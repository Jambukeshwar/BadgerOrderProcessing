// ============================================================
// DISCONNECT ORDER SUBMIT — null JSON detection + merge + enqueue
//   {ORDER_ID} → substituted by Python before executeAnonymous
// ============================================================

Id orderId = '{ORDER_ID}';

List<OrderItem> orderItems = [
    SELECT Id, vlocity_cmt__JSONAttribute__c
    FROM OrderItem
    WHERE OrderId = :orderId
];

System.debug('Total OrderItems found: ' + orderItems.size());

Boolean hasNullJsonIssue = false;
if (orderItems != null) {
    for (OrderItem o : orderItems) {
        if (o != null && o.vlocity_cmt__JSONAttribute__c == null) {
            hasNullJsonIssue = true;
            System.debug('Null JSONAttribute detected on OrderItem Id: ' + o.Id);
            break;
        }
    }
}

System.debug('hasNullJsonIssue: ' + hasNullJsonIssue);

if (hasNullJsonIssue) {
    System.debug('Null issue found — Starting JSON merge...');

    Map<String, Object> parsedJsonNew = new Map<String, Object>();
    if (orderItems != null) {
        for (OrderItem o : orderItems) {
            if (o != null && o.vlocity_cmt__JSONAttribute__c != null) {
                Map<String, Object> parsedJson = (Map<String, Object>) JSON.deserializeUntyped(o.vlocity_cmt__JSONAttribute__c);
                if (parsedJson != null) {
                    parsedJsonNew.putAll(parsedJson);
                    System.debug('Merged JSON from OrderItem: ' + o.Id);
                }
            }
        }
    }

    System.debug('Final Merged JSON: ' + parsedJsonNew);

    if (orderItems != null) {
        for (OrderItem o : orderItems) {
            if (o != null) {
                o.vlocity_cmt__JSONAttribute__c = JSON.serialize(parsedJsonNew);
            }
        }
    }

    if (orderItems != null && orderItems.size() > 0) {
        update orderItems;
        System.debug('OrderItems updated successfully with merged JSON.');
    }
} else {
    System.debug('No null issue found — Skipping JSON merge, proceeding to submit.');
}

List<Order> orders = [
    SELECT Id, vlocity_cmt__FulfilmentStatus__c, vlocity_cmt__OrderStatus__c
    FROM Order
    WHERE Id = :orderId
];

if (orders != null) {
    for (Order o : orders) {
        if (o != null && o.Id != null) {
            ID jobID = System.enqueueJob(new PR_CartSubmitQueueable(o.Id));
            System.debug('Order submitted — jobID: ' + jobID);
        }
    }
}

System.debug('Script execution completed.');
