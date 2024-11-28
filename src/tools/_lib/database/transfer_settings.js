function transferSettings(mongoSourceURI, mongoDestinationURI, sourceDbName, targetDbName) {
    const sourceDb = connect(`${mongoSourceURI}/${sourceDbName}`);
    const targetDb = connect(`${mongoDestinationURI}/${targetDbName}`);

    const sourceSettings = sourceDb.getCollection('settings');
    const targetSettings = targetDb.getCollection('settings');

    // Delete the target settings collection if it exists
    if (targetDb.getCollectionNames().includes('settings')) {
        targetDb.getCollection('settings').drop();
    }
    // Find all documents in source.settings except "local_settings" and "versions_order"
    settingsDocuments = sourceSettings.find({
        type: { $nin: ["local_settings", "versions_order"] }
    }).toArray();

    latestVersionedSettings = {};
    latestVersionedAnatomy = null;
    latestVersionedSystemSettings = null;

    // Insert each document into the target.settings collection
    settingsDocuments.forEach(function(document) {
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

        if (document.version) {
            document.version = "4.0.0";
        }

        if (document.type === "system_settings"){
            document.type = "global_settings";
            document.data.core = document.data.general;
            delete document.data.general;
            targetSettings.insert(document);
            return
        }

        if (document.type === "global_settings") {
            document.type = "core_settings";
            document.data.production_version = "4.0.0";
            document.data.staging_version = "4.0.0";
            document.data.remote_versions_dirs = document.data.openpype_path;
            delete document.data.openpype_path;
            targetSettings.insert(document);
            return
        }

        if (document.type === "project_anatomy_versioned") {
            if (document.last_saved_info && document.last_saved_info.timestamp) {
                const timestamp = new Date(document.last_saved_info.timestamp);
                if (!latestVersionedAnatomy || timestamp > new Date(latestVersionedAnatomy.last_saved_info.timestamp)) {
                    latestVersionedAnatomy = document;
                }
            }
            return
        }

        if (document.type === "system_settings_versioned") {
            document.type = "global_settings_versioned"
            document.data.core = document.data.general;
            delete document.data.modules.addon_paths;
            document.data.addons = document.data.modules;
            delete document.data.general;
            delete document.data.modules;
            if (document.last_saved_info && document.last_saved_info.timestamp) {
                const timestamp = new Date(document.last_saved_info.timestamp);
                if (!latestVersionedSystemSettings || timestamp > new Date(latestVersionedSystemSettings.last_saved_info.timestamp)) {
                    latestVersionedSystemSettings = document;
                }
            }
            return
        }

        if (document.type === "project_settings_versioned") {
            if (document.last_saved_info && document.last_saved_info.timestamp && document.project_name) {
                const projectName = document.project_name;
                const timestamp = new Date(document.last_saved_info.timestamp);

                if (!latestVersionedSettings[projectName]) {
                    latestVersionedSettings[projectName] = document;
                } else {
                    const existingTimestamp = new Date(latestVersionedSettings[projectName].last_saved_info.timestamp);
                    if (timestamp > existingTimestamp) {
                        latestVersionedSettings[projectName] = document;
                    }
                }
            }
            return
        }
    });

    // Insert Latest Versioned Anatomy Settings
    if (latestVersionedAnatomy) {
        targetSettings.insert(latestVersionedAnatomy);
    }

    // Insert Latest Versioned System Settings
    if (latestVersionedSystemSettings) {
        targetSettings.insert(latestVersionedSystemSettings);
    }

    // Insert Latest Versioned Settings for each Project
    Object.values(latestVersionedSettings).forEach(function(latestDocument) {
        targetSettings.insert(latestDocument);
    });

    const sourceDbProjectsDb = connect(`${mongoSourceURI}/avalon`);
    const targetDbProjectsDb = connect(`${mongoDestinationURI}/${targetDbName}_projects`);
    collections = sourceDbProjectsDb.getCollectionNames();
    collections.forEach(collectionName => {
        sourceCollection = sourceDbProjectsDb.getCollection(collectionName);
        targetCollection = targetDbProjectsDb.getCollection(collectionName);
        // Drop the target collection if it already exists
        if (targetDbProjectsDb.getCollectionNames().includes(collectionName)) {
            targetCollection.drop();
            console.log("Collection ${collectionName} dropped from target database.");
        }

        sourceCollection.find().forEach(document => {
            targetCollection.insert(document);
        });
        console.log("Collection $(collectionName) transferred to ${targetDbName}_projects database.");
    });
    console.log("Transfer completed!");
}

transferSettings(MONGO_URI, MONGO_DESTINATION, 'openpype', 'quadpype');
