/**
 * Rejected Orders Fix - Audit OrderItem & Asset line numbers, then resubmit.
 * Replace placeholders before executing:
 *   {ORDER_ID} -> Salesforce Order Id
 *   {DRY_RUN}  -> true | false
 */
Id orderId = '{ORDER_ID}';
Boolean dryRun = {DRY_RUN};

System.debug('=== REJECTED ORDER FIX: ' + orderId + ' (dryRun=' + dryRun + ') ===');

Integer itemUpdateCount  = 0;
Integer assetUpdateCount = 0;
String  resubmitMode     = '';

// ============================================================
// PHASE 1: OrderItem Hierarchy Audit
// ============================================================
List<OrderItem> items = [
    SELECT Id, Product2.Name, PR_MSISDN__c,
           vlocity_cmt__LineNumber__c, vlocity_cmt__RootItemId__c,
           vlocity_cmt__ParentItemId__c, Product2.vlocity_cmt__ParentClassCode__c
    FROM OrderItem WHERE OrderId = :orderId
];
System.debug('OrderItems found: ' + items.size());

Map<Id, Map<String, String>> itemRoots          = new Map<Id, Map<String, String>>();
Map<String, Map<String, String>> itemMsisdnRoots = new Map<String, Map<String, String>>();

for (OrderItem rec : items) {
    String pClass = (rec.Product2 != null && rec.Product2.vlocity_cmt__ParentClassCode__c != null)
        ? rec.Product2.vlocity_cmt__ParentClassCode__c : '';

    if (rec.Id == rec.vlocity_cmt__RootItemId__c && rec.vlocity_cmt__ParentItemId__c == null) {
        if (pClass == 'PR_B2C_Mobile_Line_Class' || pClass == 'PR_B2C_Mobile_Device_Class') {
            Map<String, String> rootInfo = new Map<String, String>{
                'id'  => rec.Id,
                'num' => String.valueOf(rec.vlocity_cmt__LineNumber__c)
            };
            itemRoots.put(rec.Id, rootInfo);
            if (pClass == 'PR_B2C_Mobile_Line_Class' && rec.PR_MSISDN__c != null) {
                itemMsisdnRoots.put(rec.PR_MSISDN__c, rootInfo);
            }
        }
    }
}
System.debug('OrderItem roots: ' + itemRoots.size());

Map<Id, Integer> itemSeq      = new Map<Id, Integer>();
List<OrderItem> itemsToUpdate = new List<OrderItem>();

for (OrderItem rec : items) {
    if (itemRoots.containsKey(rec.Id)) continue;

    Map<String, String> targetRoot;
    if (rec.vlocity_cmt__ParentItemId__c != null) {
        Id parentId = (Id) rec.vlocity_cmt__ParentItemId__c;
        if (itemRoots.containsKey(parentId)) {
            targetRoot = itemRoots.get(parentId);
        } else {
            continue;
        }
    } else if (rec.PR_MSISDN__c != null && itemMsisdnRoots.containsKey(rec.PR_MSISDN__c)) {
        targetRoot = itemMsisdnRoots.get(rec.PR_MSISDN__c);
    }
    if (targetRoot == null) continue;

    Id rootId       = (Id) targetRoot.get('id');
    Integer counter = itemSeq.containsKey(rootId) ? itemSeq.get(rootId) : 1;
    String paddedSeq  = String.valueOf(counter).leftPad(4, '0');
    String expectedStr = targetRoot.get('num') + '.' + paddedSeq;

    String currentStr = String.valueOf(rec.vlocity_cmt__LineNumber__c);
    if (currentStr != expectedStr) {
        rec.put('vlocity_cmt__LineNumber__c', expectedStr);
        itemsToUpdate.add(rec);
    }
    itemSeq.put(rootId, counter + 1);
}

itemUpdateCount = itemsToUpdate.size();
System.debug('OrderItem updates needed: ' + itemUpdateCount);
if (!dryRun && !itemsToUpdate.isEmpty()) {
    update itemsToUpdate;
}

// ============================================================
// PHASE 2: Asset Hierarchy Audit (if MSISDN found)
// ============================================================
String msisdn;
for (OrderItem it : items) {
    if (it.PR_MSISDN__c != null) { msisdn = it.PR_MSISDN__c; break; }
}

if (msisdn != null) {
    List<Asset> assets = [
        SELECT Id, Name, Product2.Name, PR_MSISDN__c, vlocity_cmt__LineNumber__c,
               vlocity_cmt__RootItemId__c, vlocity_cmt__ParentItemId__c,
               Product2.vlocity_cmt__ParentClassCode__c
        FROM Asset
        WHERE PR_MSISDN__c = :msisdn
        AND vlocity_cmt__ProvisioningStatus__c = 'Active'
    ];
    System.debug('Assets found for MSISDN ' + msisdn + ': ' + assets.size());

    Map<Id, Map<String, String>> assetRoots          = new Map<Id, Map<String, String>>();
    Map<String, Map<String, String>> assetMsisdnRoots = new Map<String, Map<String, String>>();

    for (Asset rec : assets) {
        String pClass = (rec.Product2 != null && rec.Product2.vlocity_cmt__ParentClassCode__c != null)
            ? rec.Product2.vlocity_cmt__ParentClassCode__c : '';

        if (rec.Id == rec.vlocity_cmt__RootItemId__c && rec.vlocity_cmt__ParentItemId__c == null) {
            if (pClass == 'PR_B2C_Mobile_Line_Class' || pClass == 'PR_B2C_Mobile_Device_Class') {
                Map<String, String> rootInfo = new Map<String, String>{
                    'id'  => rec.Id,
                    'num' => String.valueOf(rec.vlocity_cmt__LineNumber__c)
                };
                assetRoots.put(rec.Id, rootInfo);
                if (pClass == 'PR_B2C_Mobile_Line_Class' && rec.PR_MSISDN__c != null) {
                    assetMsisdnRoots.put(rec.PR_MSISDN__c, rootInfo);
                }
            }
        }
    }

    Map<Id, Integer> assetSeq    = new Map<Id, Integer>();
    List<Asset> assetsToUpdate   = new List<Asset>();

    for (Asset rec : assets) {
        if (assetRoots.containsKey(rec.Id)) continue;

        Map<String, String> targetRoot;
        if (rec.vlocity_cmt__ParentItemId__c != null) {
            Id parentId = (Id) rec.vlocity_cmt__ParentItemId__c;
            if (assetRoots.containsKey(parentId)) {
                targetRoot = assetRoots.get(parentId);
            } else {
                continue;
            }
        } else if (rec.PR_MSISDN__c != null && assetMsisdnRoots.containsKey(rec.PR_MSISDN__c)) {
            targetRoot = assetMsisdnRoots.get(rec.PR_MSISDN__c);
        }
        if (targetRoot == null) continue;

        Id rootId       = (Id) targetRoot.get('id');
        Integer counter = assetSeq.containsKey(rootId) ? assetSeq.get(rootId) : 1;
        String paddedSeq  = String.valueOf(counter).leftPad(4, '0');
        String expectedStr = targetRoot.get('num') + '.' + paddedSeq;

        String currentStr = String.valueOf(rec.vlocity_cmt__LineNumber__c);
        if (currentStr != expectedStr) {
            rec.put('vlocity_cmt__LineNumber__c', expectedStr);
            assetsToUpdate.add(rec);
        }
        assetSeq.put(rootId, counter + 1);
    }

    assetUpdateCount = assetsToUpdate.size();
    System.debug('Asset updates needed: ' + assetUpdateCount);
    if (!dryRun && !assetsToUpdate.isEmpty()) {
        update assetsToUpdate;
    }
}

// ============================================================
// PHASE 3: Reset Order Status
// ============================================================
Order o = [SELECT Id FROM Order WHERE Id = :orderId LIMIT 1];
o.Status = 'Draft';
o.vlocity_cmt__FulfilmentStatus__c = 'Draft';
o.vlocity_cmt__OrderStatus__c = 'Ready To Submit';
if (!dryRun) {
    update o;
}

// ============================================================
// PHASE 4: Resubmit (delete plan + checkout, OR enqueue)
// ============================================================
List<vlocity_cmt__OrchestrationPlan__c> plans = [
    SELECT Id FROM vlocity_cmt__OrchestrationPlan__c
    WHERE vlocity_cmt__OrderId__c = :orderId
];

if (!plans.isEmpty()) {
    resubmitMode = 'deep_reset_checkout';
    if (!dryRun) {
        delete plans;
        vlocity_cmt.CpqAppHandler cpq = new vlocity_cmt.CpqAppHandler();
        cpq.invokeMethod(
            'checkout',
            new Map<String, Object>{ 'cartId' => orderId },
            new Map<String, Object>(),
            new Map<String, Object>()
        );
    }
} else {
    resubmitMode = 'enqueue_resubmit';
    if (!dryRun) {
        System.enqueueJob(new PR_CartSubmitQueueable(orderId));
    }
}

System.debug('=== RESULT itemUpdates=' + itemUpdateCount
    + ' assetUpdates=' + assetUpdateCount
    + ' resubmit=' + resubmitMode
    + ' dryRun=' + dryRun + ' ===');
