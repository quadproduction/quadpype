/*jslint vars: true, plusplus: true, devel: true, nomen: true, regexp: true,
indent: 4, maxerr: 50 */
/*global $, Folder*/
//@include "../js/libs/json.js"

/* All public API function should return JSON! */

app.preferences.savePrefAsBool("General Section", "Show Welcome Screen", false) ;

if(!Array.prototype.indexOf) {
    Array.prototype.indexOf = function ( item ) {
        var index = 0, length = this.length;
        for ( ; index < length; index++ ) {
                  if ( this[index] === item )
                        return index;
        }
        return -1;
        };
}

function sayHello(){
    alert("hello from ExtendScript");
}

function getEnv(variable){
    return $.getenv(variable);
}

function getMetadata(){
    /**
     *  Returns payload in 'Label' field of project's metadata
     *
     **/
    if (ExternalObject.AdobeXMPScript === undefined){
        ExternalObject.AdobeXMPScript =
            new ExternalObject('lib:AdobeXMPScript');
    }

    var proj = app.project;
    var meta = new XMPMeta(app.project.xmpPacket);
    var schemaNS = XMPMeta.getNamespaceURI("xmp");
    var label = "xmp:Label";

    if (meta.doesPropertyExist(schemaNS, label)){
        var prop = meta.getProperty(schemaNS, label);
        return prop.value;
    }

    return _prepareSingleValue([]);

}

function imprint(payload){
    /**
     * Stores payload in 'Label' field of project's metadata
     *
     * Args:
     *     payload (string): json content
     */
    if (ExternalObject.AdobeXMPScript === undefined){
        ExternalObject.AdobeXMPScript =
            new ExternalObject('lib:AdobeXMPScript');
    }

    var proj = app.project;
    var meta = new XMPMeta(app.project.xmpPacket);
    var schemaNS = XMPMeta.getNamespaceURI("xmp");
    var label = "xmp:Label";

    meta.setProperty(schemaNS, label, payload);

    app.project.xmpPacket = meta.serialize();

}


function fileOpen(path){
    /**
     * Opens (project) file on 'path'
     */
    fp = new File(path);
    return _prepareSingleValue(app.open(fp))
}

function getActiveDocumentName(){
    /**
     *   Returns file name of active document
     * */
    var file = app.project.file;

    if (file){
        return _prepareSingleValue(file.name)
    }

    return _prepareError("No file open currently");
}

function getActiveDocumentFullName(){
    /**
     *   Returns absolute path to current project
     * */
    var file = app.project.file;

    if (file){
        var f = new File(file.fullName);
        var path = f.fsName;
        f.close();

        return _prepareSingleValue(path)
    }

    return _prepareError("No file open currently");
}


function addItem(name, item_type){
    /**
     * Adds comp or folder to project items.
     *
     * Could be called when creating publishable instance to prepare
     * composition (and render queue).
     *
     * Args:
     *      name (str): composition name
     *      item_type (str): COMP|FOLDER
     * Returns:
     *      SingleItemValue: eg {"result": VALUE}
     */
    if (item_type == "COMP"){
        // dummy values, will be rewritten later
        item = app.project.items.addComp(name, 1920, 1060, 1, 10, 25);
    }else if (item_type == "FOLDER"){
        item = app.project.items.addFolder(name);
    }else{
        return _prepareError("Only 'COMP' or 'FOLDER' can be created");
    }
    return _prepareSingleValue(item.id);

}

function getItems(comps, folders, footages){
    /**
     * Returns JSON representation of compositions and
     * if 'collectLayers' then layers in comps too.
     *
     * Args:
     *     comps (bool): return selected compositions
     *     folders (bool): return folders
     *     footages (bool): return FootageItem
     * Returns:
     *     (list) of JSON items
     */
    var items = []
    for (i = 1; i <= app.project.items.length; ++i){
        var item = app.project.items[i];
        if (!item){
            continue;
        }
        var ret = _getItem(item, comps, folders, footages);
        if (ret){
            items.push(ret);
        }
    }
    return '[' + items.join() + ']';

}

function selectItems(items){
    /**
     * Select all items from `items`, deselect other.
     *
     * Args:
     *      items (list)
     */
    for (i = 1; i <= app.project.items.length; ++i){
        item = app.project.items[i];
        if (items.indexOf(item.id) > -1){
            item.selected = true;
        }else{
            item.selected = false;
        }
    }

}

function getSelectedItems(comps, folders, footages){
    /**
     * Returns list of selected items from Project menu
     *
     * Args:
     *     comps (bool): return selected compositions
     *     folders (bool): return folders
     *     footages (bool): return FootageItem
     * Returns:
     *     (list) of JSON items
     */
    var items = []
    for (i = 0; i < app.project.selection.length; ++i){
        var item = app.project.selection[i];
        if (!item){
            continue;
        }
        var ret = _getItem(item, comps, folders, footages);
        if (ret){
            items.push(ret);
        }
    }
    return '[' + items.join() + ']';
}

function _getItem(item, comps, folders, footages){
    /**
     * Auxiliary function as project items and selections
     * are indexed in different way :/
     * Refactor
     */
    var item_type = '';
    var path = '';
    var containing_comps = [];
    if (item instanceof FolderItem){
        item_type = 'folder';
        if (!folders){
            return "{}";
        }
    }
    if (item instanceof FootageItem){
        if (!footages){
            return "{}";
        }
        item_type = 'footage';
        if (item.file){
            path = item.file.fsName;
        }
        if (item.usedIn){
            for (j = 0; j < item.usedIn.length; ++j){
                containing_comps.push(item.usedIn[j].id);
            }
        }
    }
    if (item instanceof CompItem){
        item_type = 'comp';
        if (!comps){
            return "{}";
        }
    }

    var item = {"name": item.name,
                "id": item.id,
                "type": item_type,
                "path": path,
                "containing_comps": containing_comps};
    return JSON.stringify(item);
}

function importFile(path, item_name, import_options){
    /**
     * Imports file (image tested for now) as a FootageItem.
     * Creates new composition
     *
     * Args:
     *    path (string): absolute path to image file
     *    item_name (string): label for composition
     * Returns:
     *    JSON {name, id}
     */
    if (!import_options) { import_options = "{}"; }

    var comp;
    var ret = {};
    try{
        import_options = JSON.parse(import_options);
    } catch (e){
        return _prepareError("Couldn't parse import options " + import_options);
    }

    app.beginUndoGroup("Import File");
    fp = new File(path);
    if (fp.exists){
        try {
            im_opt = new ImportOptions(fp);
            importAsType = import_options["ImportAsType"];

            if ('ImportAsType' in import_options){ // refactor
                if (importAsType.indexOf('COMP') > 0){
                    im_opt.importAs = ImportAsType.COMP;
                }
                if (importAsType.indexOf('FOOTAGE') > 0){
                    im_opt.importAs = ImportAsType.FOOTAGE;
                }
                if (importAsType.indexOf('COMP_CROPPED_LAYERS') > 0){
                    im_opt.importAs = ImportAsType.COMP_CROPPED_LAYERS;
                }
                if (importAsType.indexOf('PROJECT') > 0){
                    im_opt.importAs = ImportAsType.PROJECT;
                }

            }
            if ('sequence' in import_options){
                im_opt.sequence = true;
            }

            comp = app.project.importFile(im_opt);

            if (app.project.selection.length == 2 &&
                app.project.selection[0] instanceof FolderItem){
                 comp.parentFolder = app.project.selection[0]
            }

            if (import_options.hasOwnProperty("fps") && import_options.hasOwnProperty("sequence")){
                comp.mainSource.conformFrameRate = import_options["fps"];
            }

        } catch (error) {
            return _prepareError(error.toString() + importOptions.file.fsName);
        } finally {
            fp.close();
        }
    }else{
	    return _prepareError("File " + path + " not found.");
    }
    if (comp){
        comp.name = item_name;
        comp.label = 9; // Green
        ret = {"name": comp.name, "id": comp.id}
    }
    app.endUndoGroup();

    return JSON.stringify(ret);
}

function _pathIsFile(path){
    return path.match(new RegExp(".[a-zA-Z]{3}$"));
}

function importFileWithDialog(path, item_name, import_options){
    if (!import_options) { import_options = "{}"; }

    app.beginUndoGroup("Import");

    try{
        import_options = JSON.parse(import_options);
    } catch (e){
        return _prepareError("Couldn't parse import options " + import_options);
    }

    var importedObjects = _importFileWithDialog(path, item_name, import_options)
    if (typeof importedObjects === 'string') {
        // We return the object because it's a string error
        return importedObjects;
    }

    var importedComp = importedObjects[0]
    ret = {"name": importedComp.name, "id": importedComp.id}
    app.endUndoGroup();

    return JSON.stringify(ret);
}

function _importFileWithDialog(path, item_name, import_options){
    if (!import_options) { import_options = {}; }

    var folderPath = undefined;
    if (_pathIsFile(path)){
        folderPath = new Folder(path.match(new RegExp("(.*)[/\\\\]"))[0] || '')
    } else {
        folderPath = new Folder(path)
    }

    app.project.setDefaultImportFolder(new Folder(folderPath));
    importedCompArray = app.project.importFileWithDialog();
    app.project.setDefaultImportFolder();

    if (importedCompArray === undefined){
        // User has canceled the action, so we stop the script here
        // and return an empty value to avoid parse errors later
        return ''
    }

    importedComp = importedCompArray[0]
    if (importedComp.layers === undefined){
        undoLastActions();
        return _prepareError('Wrong file type imported (impossible to access layers composition).');
    }

    importedCompFilePath = getCompFilepath(importedComp);

    if (importedCompFilePath === undefined){
        undoLastActions();
        return _prepareError('Wrong file type imported (impossible to access layers composition).');
    }

    if (extensionsAreDifferents(importedCompFilePath, path)){
        undoLastActions();
        return _prepareError('Wrong file selected (incorrect extension).');
    }

    if (versionsAreDifferents(importedCompFilePath, path)){
        undoLastActions();
        return _prepareError('Wrong file selected (incorrect asset / version).');
    }

    try {
        importedCompFolder = getImportedCompFolder(importedComp);

        importedCompFolder.name = item_name;
        importedComp.name = item_name;

        renameFolderItems(importedCompFolder);

        if (import_options.hasOwnProperty("fps") && import_options.hasOwnProperty("sequence")){
            fps = import_options['fps']
            importedComp.frameRate = fps;
            setFolderItemsFPS(importedCompFolder, fps);
        }
    } catch (error) {
        return _prepareError(error.toString() + item_name);
    }

    return [importedComp, importedCompFolder];
}


function getCompFilepath(compItem){
    for (var indexLayer = 1; indexLayer <= compItem.numLayers; indexLayer++) {
        // search if source.file is available aka the layer is not a comp
        //if one is present , it returns the path
        if (compItem.layers[indexLayer].source.file){
            return String(compItem.layers[indexLayer].source.file)
        }
    }
    // Else if none is present, must search in the imported folder of AE for layer.
    var folder = getImportedCompFolder(compItem);
    for (var indexItem = 1; indexItem <= folder.items.length; indexItem++) {
        var folderItem = folder.items[indexItem];
        // if item is a footage, get its file path
        if (folderItem instanceof FootageItem){
            return String(folderItem.file);
        }
    }
    return undefined;
}


function _extractInfosFromPath(filePath){
    return filePath.match(/(.*)[\/\\](.*)[.](.*)[.](.*)/);
}


function getFileNameFromPath(filePath){
    return _extractInfosFromPath(filePath)[2]
}


function getExtensionFromPath(filePath){
    return _extractInfosFromPath(filePath)[4]
}


function versionsAreDifferents(sourceFilePath, targetFilePath){
    return getFileNameFromPath(sourceFilePath) != getFileNameFromPath(targetFilePath);
}


function extensionsAreDifferents(sourceFilePath, targetFilePath){
    return getExtensionFromPath(sourceFilePath) != getExtensionFromPath(targetFilePath)
}


function _extractFirstPart(layerName){
    var decomposedName = layerName.match(/.+?(?=[\/])/);
    if (decomposedName === null){ return layerName; }
    else{ return decomposedName[0]; }
}


function _startsWith(source, target) {
    return source.lastIndexOf(target, 0) === 0;
}


function getImportedCompFolder(importedComp){
    for (var index = 1; index <= app.project.numItems; index++) {
        if(
            (_startsWith(app.project.item(index).name, importedComp.name)) &&
            (app.project.item(index) instanceof FolderItem)
        ){
            return app.project.item(index);
        }
    }
}

function getLayerFromFolder(folder, layerName){
    for (var index = 1; index <= folder.items.length; index++) {
        if(folder.items[index].name === layerName){
            return folder.items[index];
        }
    }
    return undefined
}

function renameFolderItems(folder){
    for (var index = 1; index <= folder.items.length; index++) {
        folderItem = folder.items[index];
        folderItem.name = _extractFirstPart(folderItem.name);
    }

}


function setFolderItemsFPS(folder, fps){
    for (var index = 1; index <= folder.items.length; index++) {
        folderItem = folder.items[index]
        folderItem.mainSource.conformFrameRate = fps
    }
}


function undoLastActions(){
    // We call the last undo command in Edit > Undo, which corresponds to
    // our script actions and whose ID is 16
    // This information has been found in AECC Menu IDs list, accessible at
    // https://www.provideocoalition.com/after-effects-menu-command-ids/
    app.endUndoGroup();
    app.executeCommand(16);
}


function setLabelColor(comp_id, color_idx){
    /**
     * Set item_id label to 'color_idx' color
     * Args:
     *     item_id (int): item id
     *     color_idx (int): 0-16 index from Label
     */
    var item = app.project.itemByID(comp_id);
    if (item){
        item.label = color_idx;
    }else{
        return _prepareError("There is no composition with "+ comp_id);
    }
}

function isComp(item){
    return (item instanceof CompItem)
}

function replaceItem(item_id, path, item_name){
    /**
     * Replaces loaded file with new file and updates name
     *
     * Args:
     *    item_id (int): id of composition, not a index!
     *    path (string): absolute path to new file
     *    item_name (string): new composition name
     */
    app.beginUndoGroup("Replace File");

    fp = new File(path);
    if (!fp.exists){
        return _prepareError("File " + path + " not found.");
    }
    var item = app.project.itemByID(item_id);

    if (item) {
        try {
            if (isComp(item)){
                result = replaceCompSequenceItems(item, path, item_name)
                if (!result) {
                    return ''
                }
            } else if (isFileSequence(item)) {
                item.replaceWithSequence(fp, false);
            } else {
                item.replace(fp);
            }

            item.name = item_name;
        } catch (error) {
            return _prepareError(error.toString() + path);
        } finally {
            fp.close();
        }
    }else{
        return _prepareError("There is no item with "+ item_id);
    }
    app.endUndoGroup();
}

function replaceCompSequenceItems(item, path, item_name){
    /**
     * Replaces all elements from given composition with selected comp.
     * It will also delete elements that are absent in newer version
     * and add newer elements to already loaded composition.
     *
     * Args:
     *    item_id (int): id of composition, not a index!
     *    path (string): absolute path to new file
     *    item_name (string): new composition name
     */

    var previousCompFolder = getImportedCompFolder(item);

    var importedObjects = _importFileWithDialog(path, item_name, undefined)
    if (typeof importedObjects === 'string') {
        // We return the object because it's a string error
        return importedObjects
    }

    var importedComp = importedObjects[0]
    var importedFolder = importedObjects[1]

    var deletedLayers = [];
    for (var index = 1; index <= item.numLayers; index++) {
        var sourceLayer = item.layer(index);
        var targetLayer = getLayerFromFolder(importedFolder, sourceLayer.name);
        if (targetLayer){
            sourceLayer.replaceSource(targetLayer, true);
        } else {
            deletedLayers.push(sourceLayer);
        }
    }

    var newLayers = _list_new_layers(item, importedComp);

    var layersToDelete = deletedLayers.length > 0;
    var layersToAdd = newLayers.length > 0;

    if (layersToDelete || layersToAdd){

        var firstPartMsg = ''
        var secondPartMsg = ''
        if (layersToDelete){ firstPartMsg = "\n- " + deletedLayers.length + " element(s) have been deleted."}
        if (layersToAdd){ secondPartMsg = "\n- " + newLayers.length + " element(s) have been added."}

        var importConfirmation = confirm(
            "Composition '" + item.name +
            "' :" + firstPartMsg + secondPartMsg + "\nDo you want to continue import ?"
        )
        if (!(importConfirmation)){
            // User has canceled the action, so we stop the script here
            // and return an empty value to avoid parse errors later
            undoLastActions();
            return ''
        }

        if (layersToDelete) { _delete_layers_dialog(item, deletedLayers); }
        if (layersToAdd) { _add_new_layers_dialog(item, importedComp, newLayers); }

    }

    importedComp.remove();
    previousCompFolder.remove();
}


function _delete_layers_dialog(compItem, deletedLayers){
    /**
     * Delete all elements in given compItem that are
     * listed in given deletedLayers array.
     * A prompt ask for confirmation before deletion.
     * Args:
     *    compItem(compItem): given compItem on which we wants to perform deletion
     *    deletedLayers(array): array of layers to delete.
     */

    var deletionConfirmation = confirm(
        "Do you want to delete the following elements from composition '" +
        compItem.name + "' :\n -" +
        deletedLayers.map(function(layer){ return layer.name }).join('\n -')
    );
    if (deletionConfirmation){
        for (var index = 0; index < deletedLayers.length; index++) {
            deletedLayers[index].remove();
        }
    }

}


function _list_new_layers(compItem, importedComp){
    /**
     * List all layers added in importedComp that are
     * missing from compItem.
     * * Args:
     *    compItem(compItem): given compItem in which the layers may be missing
     *    importedComp(compItem): compItem with potentially new layers
     */

    var additionalLayers = []
    for (var index=1; index <= importedComp.numLayers; index++){
        var target_layer = importedComp.layer(index)
        var source_layer = compItem.layer(target_layer.name)
        if (!(source_layer)){
            additionalLayers.push(target_layer);
        }
    }
    return additionalLayers
}


function _add_new_layers_dialog(compItem, importedComp, newLayers){
    /**
     * Add in composition all imported elements from
     * importedComp that are missing in compItem.
     * A prompt ask for confirmation before addition.
     * Args:
     *    compItem(compItem): given compItem in which we wants to add missing layers
     *    importedComp(compItem): compItem used for comparison
     */
    var additionConfirmation = confirm(
        "New elements have been detected in newer version. Do you want to add them to composition '" +
        compItem.name + "' ?\n -" +
        newLayers.map(function(layer){ return layer.name }).join('\n -')
    );
    if (additionConfirmation){
        for(var index=0; index < newLayers.length; index++){

            var additionalLayer = newLayers[index]
            additionalLayer.copyToComp(compItem)
            var duplicatedLayer = compItem.layer(additionalLayer.name)
            var targetIndex = importedComp.layer(duplicatedLayer.name).index

            if (targetIndex === duplicatedLayer.index){ continue; }

            duplicatedLayer.moveAfter(compItem.layer(targetIndex))
        }
    }
}

function renameItem(item_id, new_name){
    /**
     * Renames item with 'item_id' to 'new_name'
     *
     * Args:
     *    item_id (int): id to search item
     *    new_name (str)
     */
    var item = app.project.itemByID(item_id);
    if (item){
        item.name = new_name;
    }else{
        return _prepareError("There is no composition with "+ comp_id);
    }
}

function addCompToRenderQueue(comp_id){
    var comp = app.project.itemByID(comp_id);
    if (isComp(comp)) {
        var renderQueueItem = app.project.renderQueue.items.add(comp);
        renderQueueItem.outputModule(1).file = new File("C:/temp/render_output.mov");

    } else {
        return _prepareError("The following item is not a comp : "+ comp.name);
    }
}

function parentItems(item_id, parent_item_id){
    var childItem = app.project.itemByID(item_id);
    var parentFolder = app.project.itemByID(parent_item_id);
    if (childItem && parentFolder){
        childItem.parentFolder = parentFolder;
    }else{
        return _prepareError("There is a problem with "+ parentFolder.name + "or" + childItem.name);
    }
}

function deleteItem(item_id){
    /**
     *  Delete any 'item_id'
     *
     *  Not restricted only to comp, it could delete
     *  any item with 'id'
     */
    var item = app.project.itemByID(item_id);
    if (item){
        item.remove();
    }else{
        return _prepareError("There is no composition with "+ comp_id);
    }
}

function getCompProperties(comp_id){
    /**
     * Returns information about composition - are that will be
     * rendered.
     *
     * Returns
     *     (dict)
     */
    var comp = app.project.itemByID(comp_id);
    if (!comp){
        return _prepareError("There is no composition with "+ comp_id);
    }

    return JSON.stringify({
        "id": comp.id,
        "name": comp.name,
        "frameStart": comp.displayStartFrame,
        "framesDuration": comp.duration * comp.frameRate,
        "frameRate": comp.frameRate,
        "width": comp.width,
        "height": comp.height});
}

function setCompProperties(comp_id, frameStart, framesCount, frameRate,
                           width, height){
    /**
     * Sets work area info from outside (from Ftrack via QuadPype)
     */
    var comp = app.project.itemByID(comp_id);
    if (!comp){
        return _prepareError("There is no composition with "+ comp_id);
    }

    app.beginUndoGroup('change comp properties');
        if (frameStart && framesCount && frameRate){
            comp.displayStartFrame = frameStart;
            comp.duration = framesCount / frameRate;
            comp.frameRate = frameRate;
        }
        if (width && height){
            var widthOld = comp.width;
            var widthNew = width;
            var widthDelta = widthNew - widthOld;

            var heightOld = comp.height;
            var heightNew = height;
            var heightDelta = heightNew - heightOld;

            var offset = [widthDelta / 2, heightDelta / 2];

            comp.width = widthNew;
            comp.height = heightNew;

            for (var i = 1, il = comp.numLayers; i <= il; i++) {
                var layer = comp.layer(i);
                var positionProperty = layer.property('ADBE Transform Group').property('ADBE Position');

                if (positionProperty.numKeys > 0) {
                    for (var j = 1, jl = positionProperty.numKeys; j <= jl; j++) {
                        var keyValue = positionProperty.keyValue(j);
                        positionProperty.setValueAtKey(j, keyValue + offset);
                    }
                } else {
                    var positionValue = positionProperty.value;
                    positionProperty.setValue(positionValue + offset);
                }
            }
        }

    app.endUndoGroup();
}

function save(){
    /**
     * Saves current project
     */
    app.project.save();  //TODO path is wrong, File instead
}

function saveAs(path){
    /**
     *   Saves current project as 'path'
     * */
    app.project.save(fp = new File(path));
}

function getRenderInfo(comp_id){
    /***
        Get info from render queue.
        Currently pulls only file name to parse extension and
        if it is sequence in Python
    Args:
        comp_id (int): id of composition
     Return:
        (list) [{file_name:"xx.png", width:00, height:00}]
    **/
    var item = app.project.itemByID(comp_id);
    if (!item){
        return _prepareError("Composition with '" + comp_id + "' wasn't found! Recreate publishable instance(s)")
    }

    var comp_name = item.name;
    var output_metadata = []
    try{
        // render_item.duplicate() should create new item on renderQueue
        // BUT it works only sometimes, there are some weird synchronization issue
        // this method will be called always before render, so prepare items here
        // for render to spare the hassle
        for (i = 1; i <= app.project.renderQueue.numItems; ++i){
            var render_item = app.project.renderQueue.item(i);
            if (render_item.comp.id != comp_id){
                continue;
            }

            if (render_item.status == RQItemStatus.DONE){
                render_item.duplicate();  // create new, cannot change status if DONE
                render_item.remove();  // remove existing to limit duplications
                continue;
            }
        }

        // properly validate as `numItems` won't change magically
        var comp_id_count = 0;
        for (i = 1; i <= app.project.renderQueue.numItems; ++i){
            var render_item = app.project.renderQueue.item(i);
            if (render_item.comp.id != comp_id){
                continue;
            }
            comp_id_count += 1;

            for (j = 1; j<= render_item.numOutputModules; ++j){

                var item = render_item.outputModule(j);
                var file_url = item.file.toString();
                var settings = item.getSettings(GetSettingsFormat.STRING)
                var format = settings['Format']

                export_data = {
                    "file_name": file_url,
                    "width": render_item.comp.width,
                    "height": render_item.comp.height,
                    "format": format
                }

                if (settings.hasOwnProperty['Resize to']){
                    export_data['resize'] = {
                        "x": settings['Resize to']['x'],
                        "y": settings['Resize to']['y']
                    }
                }

                output_metadata.push(
                    JSON.stringify(export_data)
                );
            }
        }
    } catch (error) {
        return _prepareError("There is no render queue, create one");
    }

    if (comp_id_count > 1){
        return _prepareError("There cannot be more items in Render Queue for '" + comp_name + "'!")
    }

    if (comp_id_count == 0){
        return _prepareError("There is no item in Render Queue for '" + comp_name + "'! Add composition to Render Queue.")
    }

    return '[' + output_metadata.join() + ']';
}

function getAudioUrlForComp(comp_id){
    /**
     * Searches composition for audio layer
     *
     * Only single AVLayer is expected!
     * Used for collecting Audio
     *
     * Args:
     *    comp_id (int): id of composition
     * Return:
     *    (str) with url to audio content
     */
    var item = app.project.itemByID(comp_id);
    if (item){
        for (i = 1; i <= item.numLayers; ++i){
            var layer = item.layers[i];
            if (layer instanceof AVLayer){
                if (layer.hasAudio){
                    source_url = layer.source.file.fsName.toString()
                    return _prepareSingleValue(source_url);
                }
            }

        }
    }else{
        return _prepareError("There is no composition with "+ comp_id);
    }

}

function addItemAsLayerToComp(comp_id, item_id, found_comp){
    /**
     * Adds already imported FootageItem ('item_id') as a new
     * layer to composition ('comp_id').
     *
     * Args:
     *  comp_id (int): id of target composition
     *  item_id (int): FootageItem.id
     *  found_comp (CompItem, optional): to limit quering if
     *      comp already found previously
     */
    var comp = found_comp || app.project.itemByID(comp_id);
    if (comp){
        item = app.project.itemByID(item_id);
        if (item){
            comp.layers.add(item);
        }else{
            return _prepareError("There is no item with " + item_id);
        }
    }else{
        return _prepareError("There is no composition with "+ comp_id);
    }
}

function importBackground(comp_id, composition_name, files_to_import){
    /**
     * Imports backgrounds images to existing or new composition.
     *
     * If comp_id is not provided, new composition is created, basic
     * values (width, heights, frameRatio) takes from first imported
     * image.
     *
     * Args:
     *   comp_id (int): id of existing composition (null if new)
     *   composition_name (str): used when new composition
     *   files_to_import (list): list of absolute paths to import and
     *      add as layers
     *
     * Returns:
     *  (str): json representation (id, name, members)
     */
    var comp;
    var folder;
    var imported_ids = [];
    if (comp_id){
        comp = app.project.itemByID(comp_id);
        folder = comp.parentFolder;
    }else{
        if (app.project.selection.length > 1){
            return _prepareError(
                "Too many items selected, select only target composition!");
        }else{
            selected_item = app.project.activeItem;
            if (selected_item instanceof Folder){
                comp = selected_item;
                folder = selected_item;
            }
        }
    }

    if (files_to_import){
        for (i = 0; i < files_to_import.length; ++i){
            item = _importItem(files_to_import[i]);
            if (!item){
                return _prepareError(
                    "No item for " + item_json["id"] +
                    ". Import background failed.")
            }
            if (!comp){
                folder = app.project.items.addFolder(composition_name);
                imported_ids.push(folder.id);
                comp = app.project.items.addComp(composition_name, item.width,
                    item.height, item.pixelAspect,
                    1, 26.7);  // hardcode defaults
                imported_ids.push(comp.id);
                comp.parentFolder = folder;
            }
            imported_ids.push(item.id)
            item.parentFolder = folder;

            addItemAsLayerToComp(comp.id, item.id, comp);
        }
    }
    var item = {"name": comp.name,
                "id": folder.id,
                "members": imported_ids};
    return JSON.stringify(item);
}

function reloadBackground(comp_id, composition_name, files_to_import){
    /**
     * Reloads existing composition.
     *
     * It deletes complete composition with encompassing folder, recreates
     * from scratch via 'importBackground' functionality.
     *
     * Args:
     *   comp_id (int): id of existing composition (null if new)
     *   composition_name (str): used when new composition
     *   files_to_import (list): list of absolute paths to import and
     *      add as layers
     *
     * Returns:
     *  (str): json representation (id, name, members)
     *
     */
    var imported_ids = []; // keep track of members of composition
    comp = app.project.itemByID(comp_id);
    folder = comp.parentFolder;
    if (folder){
        renameItem(folder.id, composition_name);
        imported_ids.push(folder.id);
    }
    if (comp){
        renameItem(comp.id, composition_name);
        imported_ids.push(comp.id);
    }

    var existing_layer_names = [];
    var existing_layer_ids = []; // because ExtendedScript doesnt have keys()
    for (i = 1; i <= folder.items.length; ++i){
        layer = folder.items[i];
        //because comp.layers[i] doesnt have 'id' accessible
        if (layer instanceof CompItem){
            continue;
        }
        existing_layer_names.push(layer.name);
        existing_layer_ids.push(layer.id);
    }

    var new_filenames = [];
    if (files_to_import){
        for (i = 0; i < files_to_import.length; ++i){
            file_name = _get_file_name(files_to_import[i]);
            new_filenames.push(file_name);

            idx = existing_layer_names.indexOf(file_name);
            if (idx >= 0){  // update
                var layer_id = existing_layer_ids[idx];
                replaceItem(layer_id, files_to_import[i], file_name);
                imported_ids.push(layer_id);
            }else{ // new layer
                item = _importItem(files_to_import[i]);
                if (!item){
                    return _prepareError(
                        "No item for " + files_to_import[i] +
                        ". Reload background failed.");
                }
                imported_ids.push(item.id);
                item.parentFolder = folder;
                addItemAsLayerToComp(comp.id, item.id, comp);
            }
        }
    }

    _delete_obsolete_items(folder, new_filenames);

    var item = {"name": comp.name,
                "id": folder.id,
                "members": imported_ids};

    return JSON.stringify(item);
}

function _get_file_name(file_url){
    /**
     * Returns file name without extension from 'file_url'
     *
     * Args:
     *    file_url (str): full absolute url
     * Returns:
     *    (str)
     */
    fp = new File(file_url);
    file_name = fp.name.substring(0, fp.name.lastIndexOf("."));
    return file_name;
}

function _delete_obsolete_items(folder, new_filenames){
    /***
     * Goes through 'folder' and removes layers not in new
     * background
     *
     * Args:
     *   folder (FolderItem)
     *   new_filenames (array): list of layer names in new bg
     */
    // remove items in old, but not in new
    delete_ids = []
    for (i = 1; i <= folder.items.length; ++i){
        layer = folder.items[i];
        //because comp.layers[i] doesnt have 'id' accessible
        if (layer instanceof CompItem){
            continue;
        }
        if (new_filenames.indexOf(layer.name) < 0){
            delete_ids.push(layer.id);
        }
    }
    for (i = 0; i < delete_ids.length; ++i){
        deleteItem(delete_ids[i]);
    }
}

function _importItem(file_url){
    /**
     * Imports 'file_url' as new FootageItem
     *
     * Args:
     *    file_url (str): file url with content
     * Returns:
     *    (FootageItem)
     */
    file_name = _get_file_name(file_url);

    //importFile prepared previously to return json
    item_json = importFile(file_url, file_name, JSON.stringify({"ImportAsType":"FOOTAGE"}));
    item_json = JSON.parse(item_json);
    item = app.project.itemByID(item_json["id"]);

    return item;
}

function isFileSequence (item){
    /**
     * Check that item is a recognizable sequence
     */
    if (item instanceof FootageItem && item.mainSource instanceof FileSource && !(item.mainSource.isStill) && item.hasVideo){
        var extname = item.mainSource.file.fsName.split('.').pop();

        return extname.match(new RegExp("(ai|bmp|bw|cin|cr2|crw|dcr|dng|dib|dpx|eps|erf|exr|gif|hdr|ico|icb|iff|jpe|jpeg|jpg|mos|mrw|nef|orf|pbm|pef|pct|pcx|pdf|pic|pict|png|ps|psd|pxr|raf|raw|rgb|rgbe|rla|rle|rpf|sgi|srf|tdi|tga|tif|tiff|vda|vst|x3f|xyze)", "i")) !== null;
    }

    return false;
}

function render(target_folder, comp_id){
    var out_dir = new Folder(target_folder);
    var out_dir = out_dir.fsName;
    for (i = 1; i <= app.project.renderQueue.numItems; ++i){
        var render_item = app.project.renderQueue.item(i);
        var composition = render_item.comp;
        if (composition.id == comp_id){
            if (render_item.status == RQItemStatus.DONE){
                var new_item = render_item.duplicate();
                render_item.remove();
                render_item = new_item;
            }

            render_item.render = true;

            var targetFolder = new Folder(target_folder);
            if (!targetFolder.exists) {
                targetFolder.create();
            }

            for (j = 1; j <= render_item.numOutputModules; ++j){
                var om1 = app.project.renderQueue.item(i).outputModule(j);
                var file_name = File.decode( om1.file.name ).replace('℗', ''); // Name contains special character, space?

                om1.file = new File(targetFolder.fsName + '/' + file_name);
            }
        }else{
            if (render_item.status != RQItemStatus.DONE){
                render_item.render = false;
            }
        }

    }
    app.beginSuppressDialogs();
    app.project.renderQueue.render();
    app.endSuppressDialogs(false);
}

function close(){
    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    app.quit();
}

function getAppVersion(){
    return _prepareSingleValue(app.version);
}

function printMsg(msg){
    alert(msg);
}

function addPlaceholder(name, width, height, fps, duration){
    /** Add AE PlaceholderItem to Project list.
     *
     * PlaceholderItem chosen as it doesn't require existing file and
     * might potentially allow nice functionality in the future.
     *
     */
    app.beginUndoGroup('change comp properties');
    try{
        item = app.project.importPlaceholder(name, width, height,
                                             fps, duration);

        return _prepareSingleValue(item.id);
    }catch (error) {
        writeLn(_prepareError("Cannot add placeholder " + error.toString()));
    }
    app.endUndoGroup();
}

function addItemInstead(placeholder_item_id, item_id){
    /** Add new loaded item in place of load placeholder.
     *
     * Each placeholder could be placed multiple times into multiple
     * composition. This loops through all compositions and
     * places loaded item under placeholder.
     * Placeholder item gets deleted later separately according
     * to configuration in Settings.
     *
     * Args:
     *      placeholder_item_id (int)
     *      item_id (int)
    */
    var item = app.project.itemByID(item_id);
    if (!item){
        return _prepareError("There is no item with "+ item_id);
    }

    app.beginUndoGroup('Add loaded items');
    for (i = 1; i <= app.project.items.length; ++i){
        var comp = app.project.items[i];
        if (!(comp instanceof CompItem)){
            continue
        }

        var i = 1;
        while (i <= comp.numLayers) {
            var layer = comp.layer(i);
            var layer_source = layer.source;
            if (layer_source && layer_source.id == placeholder_item_id){
                var new_layer = comp.layers.add(item);
                new_layer.moveAfter(layer);
                // copy all(?) properties to new layer
                layer.property("ADBE Transform Group").copyToComp(new_layer);
                i = i + 1;
            }
            i = i + 1;
        }
    }
    app.endUndoGroup();
}

function _prepareSingleValue(value){
    return JSON.stringify({"result": value})
}
function _prepareError(error_msg){
    return JSON.stringify({"error": error_msg})
}
