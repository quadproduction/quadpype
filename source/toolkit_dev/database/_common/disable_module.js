db = connect('mongodb://localhost/quadpype');

all_settings = db.settings.find({ type: { $in: ['system_settings', 'system_settings_versioned'] } });

all_settings.forEach(function (system_setting) {

    if (! system_setting['data']['modules'].hasOwnProperty(moduleName)) {
        return;
    }

    system_setting['data']['modules'][moduleName]['enabled'] = false;
    db.settings.updateOne(
        { _id: system_setting['_id'] },
        { $set: { "data": system_setting['data'] } },
    );
});
