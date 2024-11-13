function transferSettings(sourceDbName, targetDbName) {
    const sourceDb = connect(`mongodb://localhost/${sourceDbName}`);
    const targetDb = connect(`mongodb://localhost/${targetDbName}`);

    const sourceSettings = sourceDb.getCollection('settings');
    const targetSettings = targetDb.getCollection('settings');

    // Find all documents in source.settings except "local_settings" and "versions_order"
    settingsDocuments = sourceSettings.find({
        type: { $nin: ["local_settings", "versions_order"] }
    }).toArray();

    latestVersionedSettings = {};

    // Insert each document into the target.settings collection
    settingsDocuments.forEach(function(document) {
        if (document.type === "global_settings") {
            document.production_version = "4.0.0";
            document.staging_version = "4.0.0";
            document.data.quadpype_path = document.data.openpype_path;
            delete document.data.openpype_path;
        }

        if (document.type === "project_settings_versioned") {
            if (!(document.last_saved_info && document.last_saved_info.timestamp && document.project_name)) {
                return;
            }
            projectName = document.project_name;
            timestamp = new Date(document.last_saved_info.timestamp);

            if (!latestVersionedSettings[projectName]) {
                latestVersionedSettings[projectName] = document;
            } else {
                existingTimestamp = new Date(latestVersionedSettings[projectName].last_saved_info.timestamp);
                if (timestamp > existingTimestamp) {
                    latestVersionedSettings[projectName] = document;
                }
            }
        } else {
            if (document.last_saved_info) {
                document.last_saved_info.quadpype_version = "4.0.0";
                document.last_saved_info.workstation_name = document.last_saved_info.hostname;
                document.last_saved_info.host_ip = document.last_saved_info.hostip;
                document.last_saved_info.user_id = document.last_saved_info.local_id;
                delete document.last_saved_info.hostname;
                delete document.last_saved_info.hostip;
                delete document.last_saved_info.local_id;
                delete document.last_saved_info.openpype_version;
            }
            targetSettings.insert(document);
        }
    });

    Object.values(latestVersionedSettings).forEach(function(latestDocument) {
        latestDocument.version = "4.0.0";
        if (latestDocument.last_saved_info) {
            latestDocument.last_saved_info.quadpype_version = "4.0.0";
            latestDocument.last_saved_info.workstation_name = latestDocument.last_saved_info.hostname;
            latestDocument.last_saved_info.host_ip = latestDocument.last_saved_info.hostip;
            latestDocument.last_saved_info.user_id = latestDocument.last_saved_info.local_id;
            delete latestDocument.last_saved_info.openpype_version;
            delete latestDocument.last_saved_info.hostname;
            delete latestDocument.last_saved_info.hostip;
            delete latestDocument.last_saved_info.local_id;
        }
        targetSettings.insert(latestDocument);
    });

    const sourceDbProjectsDb = connect(`mongodb://localhost/avalon`);
    const targetDbProjectsDb = connect(`mongodb://localhost/${targetDbName}_projects`);

    collections = sourceDbProjectsDb.getCollectionNames();
    collections.forEach(collectionName => {
        sourceCollection = sourceDbProjectsDb.getCollection(collectionName);
        targetCollection = targetDbProjectsDb.getCollection(collectionName);

        sourceCollection.find().forEach(document => {
            targetCollection.insert(document);
        });
        console.log("Collection $(collectionName) transferred to ${targetDbName}_projects database.");
    });
    console.log("Transfer complete!");
}

transferSettings('openpype', 'quadpype');
