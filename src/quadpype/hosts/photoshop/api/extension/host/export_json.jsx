#include "json_photoshop_scripting/jamEngine-min.jsxinc"
#include "json_photoshop_scripting/jamActions-min.jsxinc"
#include "json_photoshop_scripting/jamBooks-min.jsxinc"
#include "json_photoshop_scripting/jamColors-min.jsxinc"
#include "json_photoshop_scripting/jamHelpers-min.jsxinc"
#include "json_photoshop_scripting/jamJSON-min.jsxinc"
#include "json_photoshop_scripting/jamLayers-min.jsxinc"
#include "json_photoshop_scripting/jamShapes-min.jsxinc"
#include "json_photoshop_scripting/jamStyles-min.jsxinc"
#include "json_photoshop_scripting/jamText-min.jsxinc"
#include "json_photoshop_scripting/jamUtils-min.jsxinc"


function listLayersFromScene(doc){

    var layers = doc.layers;

    var retrievedLayers = []
    for (var i=0; i<layers.length; i++){
        for (var j=0; j<layers[i].layers.length; j++){
            retrievedLayers.push(layers[i].layers[j])
        }
    }

    return retrievedLayers

}

function _addLayers(layers, retrievedLayers){

    for (var i=0; i<layers.length; i++){
        if (layers[i].length > 1){ retrievedLayers = _addLayers(layers, retrievedLayers); }
        else
        {
            retrievedLayers.push(layers[i])
        }
    }

    return retrievedLayers
}


function getDocumentInfo(doc) {
    return {
        name: doc.name,
        width: doc.width.value + doc.width.type,
        height: doc.height.value + doc.height.type,
        bg: getBackgroundColor(doc),
        layers: getLayersForExport()
    };
}


function getLayersForExport() {
    /**
     * Get json representation of list of layers.
     * Similar to GetLayers base method, but adapted for json export
	 * (names are updated and we get parents names instead of parents ids).
	 * Also remove backgroundlayer handling.
     *
     * Format of single layer info:
     *      id :    number
     *      name:   string
     *      group:  boolean - true if layer is a group
     *      parents:array - list of ids of parent groups, useful for selection
     *          all children layers from parent layerSet (eg. group)
     *      type:   string - type of layer guessed from its name
     *      visible:boolean - true if visible
     **/
    if (documents.length == 0){
        return '[]';
    }
    var ref1 = new ActionReference();
    ref1.putEnumerated(charIDToTypeID('Dcmn'), charIDToTypeID('Ordn'),
                       charIDToTypeID('Trgt'));
    var count = executeActionGet(ref1).getInteger(charIDToTypeID('NmbL'));

    var layers = [];
    var parents = [];
    for (var i = count; i >= 1; i--) {
        var layer = {};
        var ref2 = new ActionReference();
        ref2.putIndex(charIDToTypeID('Lyr '), i);

        var desc = executeActionGet(ref2);  // Access layer index #i
        var layerSection = typeIDToStringID(desc.getEnumerationValue(stringIDToTypeID('layerSection')));
        layer.name = desc.getString(stringIDToTypeID("name"));

        if (layerSection == 'layerSectionStart') {
            parents.push(layer.name);
            continue;
        }
        if (layerSection == 'layerSectionEnd') {
            parents.pop();
            continue;
        }

        layer.visible = desc.getBoolean(stringIDToTypeID("visible"));
        layer.opacity = desc.getInteger(charIDToTypeID("Opct"));
        layer.blending-mode = typeIDToStringID(desc.getEnumerationValue(stringIDToTypeID('mode')));
        layer.id = desc.getInteger(stringIDToTypeID("layerID"));
        layer.parents = parents.slice();
        layer.group = getLayerColor(typeIDToStringID(desc.getEnumerationValue(stringIDToTypeID('color'))));
        layers.push(layer);
    }
    for (var i = layers.length-1; i >= 0; i--) {
        layers[i].position = i;
    }

    return layers;
}


function colorModeToString(mode) {
    switch(mode){
        case DocumentMode.BITMAP:
            return "Bitmap";
            break;
        case DocumentMode.GRAYSCALE:
            return "Grayscale";
            break;
        case DocumentMode.RGB:
            return "RGB";
            break;
        case DocumentMode.CMYK:
            return "CMYK";
            break;
        case DocumentMode.LAB:
            return "LAB";
            break;
        case DocumentMode.MULTICHANNEL:
            return "Multichannel";
            break;
        case DocumentMode.INDEXEDCOLOR:
            return "Indexed Color";
            break;
        default:
            return "Unknown"
    };
}

function getActiveChannels(doc) {
    var activeChannels = [];
    for (var i = 0; i < doc.channels.length; i++) {
        if (doc.channels[i].visible) {
            activeChannels.push(doc.channels[i].name);
        }
    }
    return activeChannels;
}

function getBackgroundColor(doc) {
    try {
        var bgColor = doc.backgroundColor;
        return colorToString(bgColor);
    } catch (e) {
        return "Unknown";
    }
}

function colorToString(color) {
    if (!color) return "None";

    try {
        if (color.rgb) {
            return "RGB(" + color.rgb.red + "," + color.rgb.green + "," + color.rgb.blue + ")";
        } else if (color.cmyk) {
            return "CMYK(" + color.cmyk.cyan + "," + color.cmyk.magenta + "," +
                   color.cmyk.yellow + "," + color.cmyk.black + ")";
        } else if (color.gray) {
            return "Gray(" + color.gray.gray + ")";
        } else if (color.lab) {
            return "LAB(" + color.lab.l + "," + color.lab.a + "," + color.lab.b + ")";
        }
    } catch (e) {
        return "Unknown color space";
    }
    return "Unknown";
}

function processLayers(layers) {
    var layerData = [];
//     for (var i = 0; i < layers.length; i++) {
//         var layerInfo = getLayerInfo(layers[i]);
//         layerInfo['position'] = i+1
//         if (layerInfo){ layerData.push(layerInfo); }
//     }
    return layerData;
}

function getLayerInfo(layer) {

    var layerInfo = {
        name: layer.name,
        type: layerKindToString(layer.kind),
        visible: layer.visible,
        opacity: layer.opacity,
        blendingMode: blendingModeToString(layer.blendMode),
        locked: layer.allLocked,
        bounds: getLayerBounds(layer),
        mask: getLayerMaskInfo(layer),
        text: layer.kind === LayerKind.TEXT ? getTextLayerInfo(layer) : null,
        smartObject: layer.kind === LayerKind.SMARTOBJECT ? getSmartObjectInfo(layer) : null,
        adjustment: isAdjustmentLayer(layer) ? getAdjustmentLayerInfo(layer) : null,
        id: layer.id,
        parent: layer.parent ? layer.parent.name : null,
        group: getLayerColor(layer),
    };

    return layerInfo;
}

function layerKindToString(kind) {
    switch(kind){
        case LayerKind.NORMAL:
            return "Normal";
            break;
        case LayerKind.TEXT:
            return "Text";
            break;
        case LayerKind.SMARTOBJECT:
            return "SmartObject";
            break;
        case LayerKind.LAYER3D:
            return "3D";
            break;
        case LayerKind.VECTOR:
            return "Vector";
            break;
        case LayerKind.ADJUSTMENT:
            return "Adjustment";
            break;
        case LayerKind.BACKGROUND:
            return "Background";
            break;
        case LayerKind.HIDDEN:
            return "Hidden";
            break;
        case LayerKind.VIDEO:
            return "Video";
            break;
        default:
            return "Unknown"
    };
}

function getLayerColor(colorCode) {
    switch(colorCode){
        case 'none':
            return {
                "red": 255,
                "green": 255,
                "blue": 255
            };
            break;
        case 'red':
            return {
                "red": 255,
                "green": 0,
                "blue": 0
            };
            break;
        case 'orange':
            return {
                "red": 255,
                "green": 128,
                "blue": 0
            };
            break;
        case 'yellowColor':
            return {
                "red": 255,
                "green": 255,
                "blue": 0
            };
            break;
        case 'grain':
            return {
                "red": 0,
                "green": 255,
                "blue": 0
            };
            break;
        case 'blue':
            return {
                "red": 0,
                "green": 0,
                "blue": 225
            };
            break;
        case 'violet':
            return {
                "red": 127,
                "green": 0,
                "blue": 255
            };
            break;
        case 'gray':
            return {
                "red": 128,
                "green": 128,
                "blue": 128
            };
            break;
        default:
            return "Unknown";
    };
}

function blendingModeToString(mode) {
    switch(mode) {
        case BlendMode.NORMAL:
            return "Normal";
            break;
        case BlendMode.DISSOLVE:
            return "Dissolve";
            break;
        case BlendMode.DARKEN:
            return "Darken";
            break;
        case BlendMode.MULTIPLY:
            return "Multiply";
            break;
        case BlendMode.COLORBURN:
            return "Color Burn";
            break;
        case BlendMode.LINEARBURN:
            return "Linear Burn";
            break;
        case BlendMode.LIGHTEN:
            return "Lighten";
            break;
        case BlendMode.SCREEN:
            return "Screen";
            break;
        case BlendMode.COLORDODGE:
            return "Color Dodge";
            break;
        case BlendMode.LINEARDODGE:
            return "Linear Dodge";
            break;
        case BlendMode.OVERLAY:
            return "Overlay";
            break;
        case BlendMode.SOFTLIGHT:
            return "Soft Light";
            break;
        case BlendMode.HARDLIGHT:
            return "Hard Light";
            break;
        case BlendMode.VIVIDLIGHT:
            return "Vivid Light";
            break;
        case BlendMode.LINEARLIGHT:
            return "Linear Light";
            break;
        case BlendMode.PINLIGHT:
            return "Pin Light";
            break;
        case BlendMode.HARDMIX:
            return "Hard Mix";
            break;
        case BlendMode.DIFFERENCE:
            return "Difference";
            break;
        case BlendMode.EXCLUSION:
            return "Exclusion";
            break;
        case BlendMode.SUBTRACT:
            return "Subtract";
            break;
        case BlendMode.DIVIDE:
            return "Divide";
            break;
        case BlendMode.HUE:
            return "Hue";
            break;
        case BlendMode.SATURATION:
            return "Saturation";
            break;
        case BlendMode.COLOR:
            return "Color";
            break;
        case BlendMode.LUMINOSITY:
            return "Luminosity";
            break;
        return "Unknown"
    };
}

function getLayerBounds(layer) {
    try {
        var bounds = layer.bounds;
        return {
            left: bounds[0].value + bounds[0].type,
            top: bounds[1].value + bounds[1].type,
            right: bounds[2].value + bounds[2].type,
            bottom: bounds[3].value + bounds[3].type,
            width: (bounds[2].value - bounds[0].value) + bounds[0].type,
            height: (bounds[3].value - bounds[1].value) + bounds[1].type
        };
    } catch (e) {
        return "Bounds not available";
    }
}

function getLayerEffects(layer) {
    app.activeDocument.activeLayer = layer
    var extraInfo = { "patterns": null };
	return jamStyles.getLayerStyle(extraInfo);
}

function getLayerMaskInfo(layer) {
    try {
        if (!layer.hasOwnProperty("layerMask")) return null;
        if (!layer.layerMask.enabled) return null;

        return {
            density: layer.layerMask.density,
            feather: layer.layerMask.feather,
            bounds: getLayerBounds(layer.layerMask)
        };
    } catch (e) {
        return null;
    }
}

function getTextLayerInfo(layer) {
    try {
        var textItem = layer.textItem;
        return {
            content: textItem.contents,
            font: textItem.font,
            size: textItem.size.value + " " + textItem.size.type,
            color: colorToString(textItem.color),
            leading: textItem.leading,
            tracking: textItem.tracking,
            horizontalScale: textItem.horizontalScale,
            verticalScale: textItem.verticalScale,
            baselineShift: textItem.baselineShift,
            fauxBold: textItem.fauxBold,
            fauxItalic: textItem.fauxItalic,
            underline: textItem.underline,
            strikeThrough: textItem.strikeThrough,
            alignment: textItem.justification,
            warpStyle: textItem.warpStyle ? textItem.warpStyle.toString() : "None",
            orientation: textItem.kind.toString()
        };
    } catch (e) {
        return null;
    }
}

function getSmartObjectInfo(layer) {
    try {
        return {
            linked: layer.linked,
            file: layer.file ? layer.file.fsName : "Embedded"
        };
    } catch (e) {
        return null;
    }
}

function isAdjustmentLayer(layer) {
    try {
        return layer.adjustment;
    } catch (e) {
        return false;
    }
}

function getAdjustmentLayerInfo(layer) {
    try {
        var adjustmentType = layer.kind.toString();
        var info = {type: adjustmentType};

        switch (adjustmentType) {
            case "solidColorLayer":
                info.color = colorToString(layer.color);
                break;
            case "gradientMapLayer":
                info.gradient = layer.gradient.name;
                break;
            case "levelsLayer":
                info.channel = layer.channel;
                info.inputRange = layer.inputRange;
                info.outputRange = layer.outputRange;
                break;
            case "curvesLayer":
                info.channel = layer.channel;
                info.curve = layer.curve;
                break;
            case "brightnessContrastLayer":
                info.brightness = layer.brightness;
                info.contrast = layer.contrast;
                break;
            case "hueSaturationLayer":
                info.hue = layer.hue;
                info.saturation = layer.saturation;
                info.lightness = layer.lightness;
                break;
            case "colorBalanceLayer":
                info.shadows = layer.shadows;
                info.midtones = layer.midtones;
                info.highlights = layer.highlights;
                break;
            case "blackWhiteLayer":
                info.reds = layer.reds;
                info.yellows = layer.yellows;
                info.greens = layer.greens;
                info.cyans = layer.cyans;
                info.blues = layer.blues;
                info.magentas = layer.magentas;
                break;
            case "photoFilterLayer":
                info.filter = layer.filter;
                info.color = colorToString(layer.color);
                info.density = layer.density;
                break;
            case "channelMixerLayer":
                info.outputChannel = layer.outputChannel;
                info.monochrome = layer.monochrome;
                break;
            case "invertLayer":
                // No additional properties
                break;
            case "posterizeLayer":
                info.levels = layer.levels;
                break;
            case "thresholdLayer":
                info.level = layer.level;
                break;
            case "selectiveColorLayer":
                info.method = layer.method;
                info.colors = layer.colors;
                break;
            case "vibranceLayer":
                info.vibrance = layer.vibrance;
                info.saturation = layer.saturation;
                break;
            default:
                info.note = "Additional properties not implemented";
        }

        return info;
    } catch (e) {
        return {type: adjustmentType, error: "Could not retrieve details"};
    }
}

function getColorInfo(doc) {
    return {
        activeForegroundColor: colorToString(app.foregroundColor),
        activeBackgroundColor: colorToString(app.backgroundColor),
        colorSamplers: getColorSamplers(doc),
        swatches: getSwatches(),
        colorSettings: getColorSettings()
    };
}

function getColorSamplers(doc) {
    try {
        var samplers = doc.colorSamplers;
        var samplerData = [];
        for (var i = 0; i < samplers.length; i++) {
            samplerData.push({
                position: {x: samplers[i].position[0].value, y: samplers[i].position[1].value},
                color: colorToString(samplers[i].color)
            });
        }
        return samplerData;
    } catch (e) {
        return [];
    }
}

function getSwatches() {
    try {
        var swatches = app.swatches;
        var swatchData = [];
        for (var i = 0; i < swatches.length; i++) {
            swatchData.push({
                name: swatches[i].name,
                color: colorToString(swatches[i].color)
            });
        }
        return swatchData;
    } catch (e) {
        return [];
    }
}

function getColorSettings() {
    try {
        return {
            workingSpaces: {
                rgb: app.rgbWorkingSpace.name,
                cmyk: app.cmykWorkingSpace.name,
                gray: app.grayWorkingSpace.name
            },
            colorManagementPolicies: {
                rgb: app.rgbColorManagementPolicy,
                cmyk: app.cmykColorManagementPolicy,
                gray: app.grayColorManagementPolicy
            },
            engine: app.colorSettings.engine,
            intent: app.colorSettings.intent,
            blackPointCompensation: app.colorSettings.blackPointCompensation
        };
    } catch (e) {
        return null;
    }
}

function getGuidesAndGrids(doc) {
    return {
        guides: getGuides(doc),
        grids: getGrids()
    };
}

function getGuides(doc) {
    try {
        var guides = doc.guides;
        var guideData = [];
        for (var i = 0; i < guides.length; i++) {
            guideData.push({
                direction: guides[i].direction.toString(),
                position: guides[i].coordinate.value + " " + guides[i].coordinate.type
            });
        }
        return guideData;
    } catch (e) {
        return [];
    }
}

function getGrids() {
    try {
        return {
            gridSize: app.preferences.gridSize,
            gridSubdivisions: app.preferences.gridSubdivisions,
            gridColor: app.preferences.gridColor.toString()
        };
    } catch (e) {
        return null;
    }
}

function getMetadata(doc) {
    try {
        var xmp = doc.xmpMetadata.rawData;
        return {
            xmp: xmp ? "XMP metadata available" : "No XMP metadata",
            exif: getExifData(doc),
            iptc: getIptcData(doc)
        };
    } catch (e) {
        return {error: "Could not retrieve metadata"};
    }
}

function getExifData(doc) {
    try {
        var exif = doc.info.exif;
        var exifData = {};
        for (var prop in exif) {
            if (exif.hasOwnProperty(prop)) {
                exifData[prop] = exif[prop].toString();
            }
        }
        return exifData;
    } catch (e) {
        return null;
    }
}

function getIptcData(doc) {
    try {
        var iptc = doc.info.iptc;
        var iptcData = {};
        for (var prop in iptc) {
            if (iptc.hasOwnProperty(prop)) {
                iptcData[prop] = iptc[prop].toString();
            }
        }
        return iptcData;
    } catch (e) {
        return null;
    }
}
