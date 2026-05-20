import subprocess
import json
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from utils.logger import Logger
from simple_salesforce import Salesforce
from automation.state_db import bulk_update_iccid_statuses

load_dotenv('.env.local')
logger = Logger().get_logger()

REPORT_FILE = Path('log') / 'order_report.csv'
_OMSUBORDERS_FILE = Path('log') / 'res_omsuborders.csv'
_SF_TTL_SECONDS = 90 * 60
_sf_client = None
_sf_ts = 0.0


def _get_sf() -> Salesforce:
    import time
    global _sf_client, _sf_ts
    if _sf_client and (time.time() - _sf_ts) < _SF_TTL_SECONDS:
        return _sf_client

    alias = os.environ.get('SF_ORG_ALIAS', 'sf-prod')
    result = subprocess.run(
        f'sf org display --target-org {alias} --json',
        shell=True, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f'SF CLI error: {result.stderr}')

    data = json.loads(result.stdout)
    _sf_client = Salesforce(
        instance_url=data['result']['instanceUrl'],
        session_id=data['result']['accessToken']
    )
    _sf_ts = time.time()
    return _sf_client


_CHUNK_SIZE = 800  # max IDs per SOQL IN clause (~18,500 chars, under SF's 20,000 limit)


def _get_order_ids_from_run() -> list[str]:
    """Read the SF Order IDs written by Badger.py into res_omsuborders.csv."""
    if not _OMSUBORDERS_FILE.exists():
        return []
    try:
        df = pd.read_csv(_OMSUBORDERS_FILE)
        if 'suborder_id' in df.columns:
            return df['suborder_id'].dropna().astype(str).tolist()
    except Exception as e:
        logger.warning(f'Could not read {_OMSUBORDERS_FILE}: {e}')
    return []


def _query_by_order_ids(sf, order_ids: list[str]) -> pd.DataFrame:
    """
    Query OrderItem by OrderId (always indexed) — fast, no QUERY_TIMEOUT.
    Returns DataFrame with PR_ICCID__c, OrderId, Order.OrderNumber, Order.Status.
    """
    frames = []
    for i in range(0, len(order_ids), _CHUNK_SIZE):
        chunk = order_ids[i:i + _CHUNK_SIZE]
        in_clause = ', '.join(f"'{v}'" for v in chunk)
        soql = (
            f"SELECT PR_ICCID__c, OrderId, Order.OrderNumber, Order.Status "
            f"FROM OrderItem "
            f"WHERE OrderId IN ({in_clause}) "
            f"LIMIT 2000"
        )
        result = sf.query(soql)
        rows = []
        for record in result.get('records', []):
            iccid = record.get('PR_ICCID__c')
            if not iccid:
                continue
            order = record.get('Order') or {}
            rows.append({
                'PR_ICCID__c':       str(iccid),
                'OrderId':           record.get('OrderId'),
                'Order.OrderNumber': order.get('OrderNumber', ''),
                'Order.Status':      order.get('Status', ''),
            })
        if rows:
            frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _query_by_iccids(sf, iccids: list[str]) -> pd.DataFrame:
    """
    Fallback: query by PR_ICCID__c (unindexed — may time out on large batches).
    Only used when res_omsuborders.csv is unavailable.
    """
    frames = []
    for i in range(0, len(iccids), _CHUNK_SIZE):
        chunk = iccids[i:i + _CHUNK_SIZE]
        in_clause = ', '.join(f"'{v}'" for v in chunk)
        soql = (
            f"SELECT PR_ICCID__c, OrderId, Order.OrderNumber, Order.Status "
            f"FROM OrderItem "
            f"WHERE PR_ICCID__c IN ({in_clause}) "
            f"AND Order.CreatedDate = LAST_N_DAYS:2 "
            f"LIMIT 2000"
        )
        result = sf.query(soql)
        rows = []
        for record in result.get('records', []):
            iccid = record.get('PR_ICCID__c')
            if not iccid:
                continue
            order = record.get('Order') or {}
            rows.append({
                'PR_ICCID__c':       str(iccid),
                'OrderId':           record.get('OrderId'),
                'Order.OrderNumber': order.get('OrderNumber', ''),
                'Order.Status':      order.get('Status', ''),
            })
        if rows:
            frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def get_already_ordered_iccids(input_iccids: list[str]) -> set:
    """
    Return the subset of input_iccids that already have an Activated Badger order
    in Salesforce OR have been successfully processed by this app before.

    Two-layer check — no QUERY_TIMEOUT risk:
      Layer 1: SQLite DB — instant, covers every date this app has run.
      Layer 2: SF query by productcode + Activated status (no PR_ICCID__c IN clause)
               — catches orders created by external systems (Integration Assistant etc.)
               regardless of date. Python filters the result against input_iccids.
    """
    from automation.state_db import get_all_created_iccids

    input_set = set(input_iccids)
    already = set()

    # Layer 1: SQLite DB
    db_created = get_all_created_iccids() & input_set
    if db_created:
        print(f'[Badger] Pre-check DB: {len(db_created)} ICCID(s) already processed by this app')
        already |= db_created

    remaining = input_set - already
    if not remaining:
        return already

    # Layer 2: SF Asset check.
    # Strategy: try PR_ICCID__c IN (chunk) — works if Asset has the field indexed.
    # If any chunk times out, fall back to fetching ALL Active Badger Assets and
    # filtering in Python (no ICCID IN clause, scales to any batch size).
    try:
        sf = _get_sf()
        sf_active  = set()
        timed_out  = False
        remaining_list = list(remaining)

        for i in range(0, len(remaining_list), _CHUNK_SIZE):
            if timed_out:
                break
            chunk     = remaining_list[i:i + _CHUNK_SIZE]
            in_clause = ', '.join(f"'{v}'" for v in chunk)
            soql = (
                f"SELECT PR_ICCID__c, vlocity_cmt__ProvisioningStatus__c "
                f"FROM Asset "
                f"WHERE product2.productcode = 'PR_B2B_Badger' "
                f"AND PR_ICCID__c IN ({in_clause})"
            )
            try:
                result = sf.query_all(soql)
                for record in result.get('records', []):
                    iccid  = record.get('PR_ICCID__c')
                    status = record.get('vlocity_cmt__ProvisioningStatus__c', '')
                    if iccid and status == 'Active':
                        sf_active.add(str(iccid))
            except Exception as chunk_err:
                if 'QUERY_TIMEOUT' in str(chunk_err):
                    print(f'[Badger] Pre-check SF: ICCID IN clause timed out — switching to full Asset fetch')
                    logger.warning('Pre-check QUERY_TIMEOUT on Asset IN clause — falling back to full fetch')
                    timed_out = True
                else:
                    raise

        if timed_out:
            # Fallback: fetch all Active Badger Assets, filter in Python
            soql = (
                "SELECT PR_ICCID__c FROM Asset "
                "WHERE product2.productcode = 'PR_B2B_Badger' "
                "AND vlocity_cmt__ProvisioningStatus__c = 'Active'"
            )
            result = sf.query_all(soql)
            all_active = set()
            for record in result.get('records', []):
                iccid = record.get('PR_ICCID__c')
                if iccid:
                    all_active.add(str(iccid))
            sf_active = all_active & remaining
            print(f'[Badger] Pre-check SF fallback: fetched {len(all_active)} Active Assets, matched {len(sf_active)} from input')

        if sf_active:
            print(f'[Badger] Pre-check SF: {len(sf_active)} ICCID(s) already Active in Asset — skipping order creation')
        already |= sf_active

    except Exception as e:
        logger.warning(f'Pre-check SF Asset query failed — skipping SF duplicate filter: {e}')
        print(f'[Badger] Pre-check SF failed ({e}) — relying on DB check only')

    logger.info(f'Pre-check total: {len(already)} of {len(input_iccids)} ICCIDs will be skipped')
    return already


DUPLICATE_REPORT_FILE = Path('log') / 'duplicate_orders_report.csv'


def check_duplicate_orders() -> pd.DataFrame:
    """
    Detect ICCIDs from this run that already have orders from ANY date in SF.

    Strategy (avoids QUERY_TIMEOUT on large unindexed IN clauses):
      Step 1 — Get today's ICCIDs via OrderId (indexed) from res_omsuborders.csv.
               Small list — fast query.
      Step 2 — Query ALL orders for those ICCIDs using PR_ICCID__c IN (small list).
               Small IN clause is acceptable even on an unindexed field.
      Step 3 — Group by ICCID; flag any with more than one OrderId as duplicate.

    Saves log/duplicate_orders_report.csv.
    Returns a DataFrame of duplicates (empty if none found).
    """
    DUPLICATE_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: get today's ICCIDs from res_omsuborders.csv via indexed OrderId query
    order_ids = _get_order_ids_from_run()
    if not order_ids:
        print('[Badger] Duplicate check: no res_omsuborders.csv — skipping')
        pd.DataFrame().to_csv(DUPLICATE_REPORT_FILE, index=False)
        return pd.DataFrame()

    sf = _get_sf()
    df_today = _query_by_order_ids(sf, order_ids)
    if df_today.empty:
        print('[Badger] Duplicate check: no OrderItems found for this run')
        pd.DataFrame().to_csv(DUPLICATE_REPORT_FILE, index=False)
        return pd.DataFrame()

    run_iccids = df_today['PR_ICCID__c'].dropna().astype(str).unique().tolist()
    print(f'[Badger] Duplicate check: querying all orders for {len(run_iccids)} ICCID(s) from this run...')

    # Step 2: query ALL orders for those ICCIDs regardless of date
    # Small IN list (just this run's ICCIDs) — acceptable even on unindexed field
    rows = []
    for i in range(0, len(run_iccids), _CHUNK_SIZE):
        chunk = run_iccids[i:i + _CHUNK_SIZE]
        in_clause = ', '.join(f"'{v}'" for v in chunk)
        soql = (
            f"SELECT PR_ICCID__c, OrderId, Order.OrderNumber, Order.Status, "
            f"Order.vlocity_cmt__OrderStatus__c, Order.CreatedBy.Name, Order.CreatedDate "
            f"FROM OrderItem "
            f"WHERE product2.productcode = 'PR_B2B_Badger' "
            f"AND PR_ICCID__c IN ({in_clause})"
        )
        try:
            result = sf.query_all(soql)
        except Exception as e:
            logger.warning(f'Duplicate check query failed: {e}')
            continue
        for record in result.get('records', []):
            iccid = record.get('PR_ICCID__c')
            if not iccid:
                continue
            order      = record.get('Order') or {}
            created_by = order.get('CreatedBy') or {}
            rows.append({
                'ICCID':              str(iccid),
                'OrderId':            record.get('OrderId', ''),
                'OrderNumber':        order.get('OrderNumber', ''),
                'OrderStatus':        order.get('Status', ''),
                'ProvisioningStatus': order.get('vlocity_cmt__OrderStatus__c', ''),
                'CreatedBy':          created_by.get('Name', ''),
                'CreatedDate':        order.get('CreatedDate', ''),
            })

    if not rows:
        print('[Badger] Duplicate check: no orders found')
        pd.DataFrame().to_csv(DUPLICATE_REPORT_FILE, index=False)
        return pd.DataFrame()

    # Step 3: flag ICCIDs with more than one order
    df = pd.DataFrame(rows)
    counts     = df.groupby('ICCID')['OrderId'].count().reset_index(name='OrderCount')
    dup_iccids = counts[counts['OrderCount'] > 1]['ICCID']

    if dup_iccids.empty:
        print('[Badger] Duplicate check: no duplicate orders found')
        pd.DataFrame().to_csv(DUPLICATE_REPORT_FILE, index=False)
        return pd.DataFrame()

    df_dupes = df[df['ICCID'].isin(dup_iccids)].sort_values(['ICCID', 'CreatedDate'])
    df_dupes.to_csv(DUPLICATE_REPORT_FILE, index=False)

    print(f'[Badger] WARNING: {len(dup_iccids)} ICCID(s) have duplicate orders — see log/duplicate_orders_report.csv')
    for iccid, grp in df_dupes.groupby('ICCID'):
        for _, r in grp.iterrows():
            print(f'  ICCID {iccid}: OrderId={r["OrderId"]} Status={r["OrderStatus"]} CreatedBy={r["CreatedBy"]} Date={r["CreatedDate"]}')

    logger.warning(f'Duplicate orders: {len(dup_iccids)} ICCID(s) affected: {list(dup_iccids)}')
    return df_dupes


def get_existing_order_iccids(iccids: list[str]) -> set:
    """
    Return the set of ICCIDs that already have an order in Salesforce.
    Uses OrderId (indexed) from res_omsuborders.csv when available.
    """
    if not iccids:
        return set()

    sf = _get_sf()
    order_ids = _get_order_ids_from_run()

    if order_ids:
        df = _query_by_order_ids(sf, order_ids)
    else:
        df = _query_by_iccids(sf, iccids)

    if df.empty:
        return set()
    return set(df['PR_ICCID__c'].dropna().astype(str))


def check_orders_created(file_id: int, input_iccids: list[str]) -> dict:
    """
    Check which ICCIDs have an OrderItem in SF created today.
    Queries by OrderId (indexed, from res_omsuborders.csv) — fast, no timeout.
    Falls back to PR_ICCID__c query if the suborders file is missing.
    Saves a detailed report to log/order_report.csv.
    Returns {'created': [...], 'needs_retry': [...]}.
    """
    if not input_iccids:
        return {'created': [], 'needs_retry': []}

    sf = _get_sf()

    order_ids = _get_order_ids_from_run()
    if order_ids:
        print(f'[Badger] Checking SF orders via {len(order_ids)} OrderId(s) (indexed query)...')
        df_orders = _query_by_order_ids(sf, order_ids)
    else:
        print(f'[Badger] res_omsuborders.csv not found — falling back to ICCID query for {len(input_iccids)} ICCIDs...')
        df_orders = _query_by_iccids(sf, input_iccids)

    print(f'[Badger] OrderItems found in SF: {len(df_orders)}')

    if df_orders.empty:
        created_set = set()
    else:
        created_set = set(df_orders['PR_ICCID__c'].dropna().astype(str))

    input_set      = set(input_iccids)
    created_iccids = list(input_set & created_set)
    retry_iccids   = list(input_set - created_set)

    # Build and save detailed report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report_rows = []

    if not df_orders.empty:
        for _, row in df_orders.iterrows():
            iccid = str(row.get('PR_ICCID__c') or '')
            if not iccid or iccid not in input_set:
                continue
            report_rows.append({
                'ICCID':       iccid,
                'OrderId':     str(row.get('OrderId') or ''),
                'OrderNumber': str(row.get('Order.OrderNumber') or ''),
                'OrderStatus': str(row.get('Order.Status') or ''),
                'Result':      'order_created',
            })

    created_in_report = {r['ICCID'] for r in report_rows}
    for iccid in retry_iccids:
        if iccid not in created_in_report:
            report_rows.append({
                'ICCID':       iccid,
                'OrderId':     '',
                'OrderNumber': '',
                'OrderStatus': '',
                'Result':      'no_order',
            })

    pd.DataFrame(report_rows).to_csv(REPORT_FILE, index=False)
    logger.info(
        f'Order check complete — created: {len(created_iccids)}, no order: {len(retry_iccids)}'
    )

    if file_id:
        status_map = {i: 'created' for i in created_iccids}
        status_map.update({i: 'failed' for i in retry_iccids})
        bulk_update_iccid_statuses(file_id, status_map)

    return {'created': created_iccids, 'needs_retry': retry_iccids}
