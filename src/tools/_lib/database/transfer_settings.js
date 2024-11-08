function transferSettings(sourceDbName, targetDbName) {
    // Connect to the databases dynamically using provided names
    const sourceDb = connect(`mongodb://localhost/${sourceDbName}`);
    const targetDb = connect(`mongodb://localhost/${targetDbName}`);

    // Define collections
    const sourceSettings = sourceDb.getCollection('settings');
    const targetSettings = targetDb.getCollection('settings');

    // Find all documents in source.settings except "local_settings"
    const settingsDocuments = sourceSettings.find({ type: { $ne: "local_settings" } }).toArray();

    // Insert each document into the target.settings collection
    settingsDocuments.forEach(function(document) {
        targetSettings.insert(document);
    });
}

// Call the function with the specific database names
transferSettings('openpype', 'quadpype');
