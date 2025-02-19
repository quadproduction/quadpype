db = connect('mongodb://localhost/quadpype');

all_settings = db.settings.find({ type: { $in: ['global_settings', 'global_settings_versioned'] } });

all_settings.forEach(function (global_setting) {
    if (!global_setting['data'].hasOwnProperty('addons')) {
        return;
    }

    if (!global_setting['data']['addons'].hasOwnProperty(moduleName)) {
        return;
    }

    global_setting['data']['addons'][moduleName]['enabled'] = false;
    db.settings.updateOne(
        { _id: global_setting['_id'] },
        { $set: { "data": global_setting['data'] } },
    );
});
