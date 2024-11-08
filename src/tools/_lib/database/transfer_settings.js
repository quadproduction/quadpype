function transferSettings(sourceDbName, targetDbName) {
    const sourceDb = connect(`mongodb://localhost/${sourceDbName}`);
    const targetDb = connect(`mongodb://localhost/${targetDbName}`);
    const sourceSettings = sourceDb.getCollection('settings');
    const targetSettings = targetDb.getCollection('settings');

    // Find all documents in source.settings except "local_settings" and "versions_order"
    const settingsDocuments = sourceSettings.find({
        type: { $nin: ["local_settings", "versions_order"] }
    }).toArray();
    // Insert each document into the target.settings collection
    settingsDocuments.forEach(function(document) {
        targetSettings.insert(document);
    });
}

transferSettings('openpype', 'quadpype');
