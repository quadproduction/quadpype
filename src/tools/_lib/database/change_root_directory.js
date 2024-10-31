db = connect('mongodb://localhost/quadpype');

all_project_anatomy = db.settings.find({ type: { $in: ['project_anatomy', 'project_anatomy_versioned'] } });

all_project_anatomy.forEach(function (project_anatomy) {

    if (! project_anatomy['data'].hasOwnProperty('roots')) {
        return;
    }

    project_anatomy['data']['roots'] = {
        work: {
          windows: rootDir,
          darwin: rootDir,
          linux: rootDir
        }
    };
    db.settings.updateOne(
        { _id: project_anatomy['_id'] },
        { $set: { "data": project_anatomy['data'] } },
    );

});
