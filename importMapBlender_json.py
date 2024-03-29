import traceback
from math import *
import io
import subprocess
import os
import json
import logging
import sys
import bpy
import importlib
import addon_utils
from time import time
from contextlib import redirect_stdout
from pathlib import Path
from configparser import BasicInterpolation, ConfigParser

# ------------------------------------
# You can edit these
_DEBUG = True       # Saves JSON files for manual Checking
_APPEND = True      # Appends the umap collections if true, otherwise it'll "link"
# If you want to edit each map seperately in their own .blends
# make this False


# ------------------------------------
# DONT TOUCH AFTER

# TODO Fix the logger
# TODO Add ability to import single .umap

stdout = io.StringIO()
os.system("cls")
sys.dont_write_bytecode = True

CWD = Path(bpy.context.space_data.text.filepath).parent
VAL_EXPORT_FOLDER = os.path.join(CWD, "export")
JSON_FOLDER = Path(os.path.join(CWD, "export", "JSONs"))
JSON_FOLDER.mkdir(parents=True, exist_ok=True)

config = ConfigParser(interpolation=BasicInterpolation())
config.read(os.path.join(CWD.__str__(), 'settings.ini'))

VAL_KEY = config["VALORANT"]["UE_AES"]
VAL_PATH = config["VALORANT"]["PATH"]
VAL_PAKS_PATH = config["VALORANT"]["PATH"] + "\live\ShooterGame\Content\Paks"
SELECTED_MAP = config["VALORANT"]["MAP"]
WHITE_RGB = (1, 1, 1, 1)
BLACK_RGB = (0, 0, 0, 0)


# // ------------------------------------
# Setup Logging

# Reset old Log File
LOGFILE = os.path.join(CWD, "yo.log")

if Path(LOGFILE).exists():
    with open(LOGFILE, "r+") as f:
        f.truncate(0)

try:
    logger
except NameError:

    # logging.getLogger("UE4Parse").setLevel(logging.INFO)
    # create logger with 'spam_application'
    logger = logging.getLogger("yo")
    logger.setLevel(logging.INFO)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(LOGFILE)
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger

    if logger.handlers.__len__() == 0:
        logger.addHandler(ch)
        logger.addHandler(fh)

try:
    sys.path.append(os.path.join(CWD.__str__()))
    sys.path.append(os.path.join(CWD.__str__(), "utils"))

    from utils import _umapList
    from utils import blenderUtils
    from utils import common
    from utils.UE4Parse.Objects.EUEVersion import EUEVersion
    from utils.UE4Parse.provider.Provider import Provider, FGame

    importlib.reload(_umapList)
    importlib.reload(blenderUtils)
    importlib.reload(common)
except Exception:
    traceback.print_exc()


def timer(func):
    # This function shows the execution time of
    # the function object passed
    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        logger.info(f'Function {func.__name__!r} executed in {(t2-t1):.3f}s')
        return result
    return wrap_func


def checkExported(f):
    if Path(f).joinpath("exported.yo").exists():
        return True
    else:
        return False


def exportAllModels():
    subprocess.call([CWD.joinpath("tools", "umodel.exe").__str__(),
                     f"-path={VAL_PAKS_PATH}",
                     f"-game=valorant",
                     f"-aes={VAL_KEY}",
                     "-export",
                     "*.uasset",
                     "-gltf",
                     "-nooverwrite",
                     f"-out={CWD.joinpath('export').__str__()}"],
                    stderr=subprocess.DEVNULL)
    with open(CWD.joinpath("export", 'exported.yo').__str__(), 'w') as out_file:
        out_file.write("")


def readJSON(f: str):
    with open(f, 'r') as jsonFile:
        data = jsonFile.read()
        return json.loads(data)


def UE4Parser(gamePath: str, aesKey: str, gameName: str = "ShooterGame", version: EUEVersion = EUEVersion.GAME_VALORANT) -> Provider:
    aeskeys = {Provider.mainGuid: aesKey}

    game = FGame()
    game.UEVersion = version
    # game.GameName = gameName

    provider = Provider(pak_folder=gamePath, GameInfo=game,
                        caseinsensitive=False)
    provider.read_paks(aeskeys)

    return provider


def cacheCheck():
    CWD.joinpath("export", "Scenes").mkdir(parents=True, exist_ok=True)

    # Check if settings.ini file set up correctly.
    # If not break the loop
    if VAL_PATH == "":
        logger.critical("You didn't setup your 'settings.ini' file!")
        return False

    # Check if everything is exported from uModel
    if checkExported(VAL_EXPORT_FOLDER):
        logger.info("Models are already extracted")
    else:
        logger.warning("Models are not found, starting exporting!")
        # Export Models
        exportAllModels()


def saveJSON(p: str, d):
    with open(p, 'w') as jsonfile:
        json.dump(d, jsonfile, indent=4)


def checkImportable(object):
    objectProperties = object["ExportValue"]

    importable_types = [
        "StaticMeshComponent",
        "InstancedStaticMeshComponent",
        "HierarchicalInstancedStaticMeshComponent"]

    BLACKLIST = ["NavMesh"]

    # if object["ExportType"] == "StaticMeshComponent" or object["ExportType"] == "InstancedStaticMeshComponent":
    if any(x == object["ExportType"] for x in importable_types):
        if "StaticMesh" in objectProperties:
            if type(objectProperties["StaticMesh"]) is dict:
                objName = object["ExportName"]
                if any(y not in objName for y in BLACKLIST):
                    return True


def getObjectname(objectProperties):
    p = Path(objectProperties["StaticMesh"]["OuterIndex"]["ObjectName"]).stem
    return p


def getObjectPath(objectProperties):
    return objectProperties["StaticMesh"]["OuterIndex"]["ObjectName"]


def getFixedPath(objectProperties):
    a = CWD.joinpath("export", os.path.splitext(
        objectProperties["StaticMesh"]["OuterIndex"]["ObjectName"])[0].strip("/")).__str__()
    return a


def getMatName(mat: dict):
    # logger.info(mat)
    return Path(mat["OuterIndex"]["ObjectName"]).name


def getMatPath(mat: dict):
    return mat["OuterIndex"]["ObjectName"]


def getFullPath(mat: dict):
    matPath = os.path.splitext(mat["OuterIndex"]["ObjectName"])[0].strip("/")
    matPathFull = CWD.joinpath("export", matPath).__str__()
    # matPathFull = matPathFull.replace("ShooterGame\Content", "Game")
    return matPathFull


def createNode(material: bpy.types.Material, lookFor: str = "", nodeName: str = "", label: str = "", pos: list = False) -> bpy.types.ShaderNode:
    # Vertex Node

    try:
        node = material.node_tree.nodes[lookFor]
    except:
        node = material.node_tree.nodes.new(nodeName)
    if pos:
        node.location.x = pos[0]
        node.location.y = pos[1]
    if label != "":
        node.label = label

    return node


def getRGB(pa: dict) -> tuple:
    return (
        pa["ParameterValue"]["R"],
        pa["ParameterValue"]["G"],
        pa["ParameterValue"]["B"],
        pa["ParameterValue"]["A"])


def setMaterial(byoMAT: bpy.types.Material, matJSON_FULL: dict, override: bool = False):

    matJSON = matJSON_FULL["Exports"][0]["ExportValue"]

    byoMAT.use_nodes = True
    byoMAT.name = matJSON_FULL["Exports"][0]["ExportName"]
    bsdf = byoMAT.node_tree.nodes["Principled BSDF"]

    defValue = 0.100
    bsdf.inputs["Specular"].default_value = defValue
    bsdf.inputs["Metallic"].default_value = defValue

    Diffuse_Map = False
    Diffuse_A_Map = False
    Diffuse_B_Map = False
    Diffuse_B_Low_Map = False

    MRA_MAP = False
    MRA_MAP_A = False
    MRA_MAP_B = False
    MRA_blendToFlat = False

    RGBA_MAP = False
    RGBA_MASK_COLOR = "R"
    MASK_MAP = False
    IMPACT_MAP = False

    Normal_Map = False
    Normal_A_Map = False
    Normal_B_Map = False

    P_texture = False

    USE_VERTEX_COLOR = False

    # Blend_Power = False

    Diffuse_Alpha_Threshold = False
    # Diffuse_Clip_Value = False
    # Diffuse_Alpha_Emission = False
    # DFEmi = False

    DF_ALPHA = False
    usesAlpha = False

    isEmissive = False
    isAdditive = False

    if override:
        imgNodePositionX = -1900.0

    else:
        imgNodePositionX = -1600.0

    vertexNode = createNode(material=byoMAT, lookFor="Vertex Color", nodeName="ShaderNodeVertexColor", label="Vertex Node", pos=[-1500.0, 1000])
    normalNode = createNode(material=byoMAT, lookFor="Normal Map", nodeName="ShaderNodeNormalMap", label="Normal Node", pos=[-400.0, -350])

    qo = 1400.0
    usedColor = (0, 0.6, 0.03)

    # Color Nodes
    Diffuse_Color = createNode(material=byoMAT, lookFor="RGB", nodeName="ShaderNodeRGB", label="DiffuseColor", pos=[-1500.0, 1400])
    byoMAT.node_tree.links.new(
        bsdf.inputs["Base Color"], Diffuse_Color.outputs["Color"])

    Layer_A_Tint = createNode(material=byoMAT, lookFor="RGB.001", nodeName="ShaderNodeRGB", label="Layer_A_TintColor", pos=[-1500.0, 1200])
    Layer_B_Tint = createNode(material=byoMAT, lookFor="RGB.002", nodeName="ShaderNodeRGB", label="Layer_B_TintColor", pos=[-1300.0, 1400])
    AO_Color = createNode(material=byoMAT, lookFor="RGB.003", nodeName="ShaderNodeRGB", label="AO_Color", pos=[-1300.0, 1200])
    Emissive_Mult = createNode(material=byoMAT, lookFor="RGB.004", nodeName="ShaderNodeRGB", label="Emissive_MultColor", pos=[-1100.0, 1400])
    Emissive_Color = createNode(material=byoMAT, lookFor="RGB.005", nodeName="ShaderNodeRGB", label="Emissive_Color", pos=[-1100.0, 1200])
    ML_Brightness = createNode(material=byoMAT, lookFor="RGB.006", nodeName="ShaderNodeRGB", label="ML_BrightnessColor", pos=[-900.0, 1400])
    LM_Vertex_Color = createNode(material=byoMAT, lookFor="RGB.006", nodeName="ShaderNodeRGB", label="Lightmass-only Vertex Color", pos=[-900.0, 1200])
    GM_color = createNode(material=byoMAT, lookFor="RGB.007", nodeName="ShaderNodeRGB", label="GM_color", pos=[-700.0, 1400])

    # Mix Nodes
    Diffuse_Mix = createNode(material=byoMAT, lookFor="Mix", nodeName="ShaderNodeMixRGB", label="DiffuseColorMix", pos=[-600.0, 1600])
    Diffuse_Mix.blend_type = 'MIX'

    if Diffuse_Mix.inputs[1].links:
        byoMAT.node_tree.links.remove(Diffuse_Mix.inputs[1].links[0])

    Layer_A_Diffuse_Tint_Mix = createNode(material=byoMAT, lookFor="Mix.001", nodeName="ShaderNodeMixRGB", label="Layer_A_Diffuse_Tint_Mix", pos=[-600.0, 1400])
    Layer_B_Diffuse_Tint_Mix = createNode(material=byoMAT, lookFor="Mix.002", nodeName="ShaderNodeMixRGB", label="Layer_B_Diffuse_Tint_Mix", pos=[-600.0, 1200])
    Layer_Z_Diffuse_Tint_Mix = createNode(material=byoMAT, lookFor="Mix.003", nodeName="ShaderNodeMixRGB", label="Layer_Z_Diffuse_Tint_Mix", pos=[-600.0, 1000])
    Layer_Z_Diffuse_Tint_Mix.inputs[0].default_value = 1
    Layer_Z_Diffuse_Tint_Mix.blend_type = 'MULTIPLY'
    Normal_Mix = createNode(material=byoMAT, lookFor="Mix.004", nodeName="ShaderNodeMixRGB", label="NormalMix", pos=[-800.0, -500])

    Vertex_Math = createNode(material=byoMAT, lookFor="Math", nodeName="ShaderNodeMath", label="VertexMath", pos=[-800.0, -500])
    Vertex_Math.operation = 'MULTIPLY'
    Vertex_Math.inputs[1].default_value = 6

    Vertex_Mix = createNode(material=byoMAT, lookFor="Mix.005", nodeName="ShaderNodeMixRGB", label="MixWithAlpha", pos=[-800.0, -500])
    Vertex_Mix.blend_type = 'LINEAR_LIGHT'
    Vertex_Mix.inputs[0].default_value = 1
    Vertex_Mix.inputs[1].default_value = WHITE_RGB

    byoMAT.node_tree.links.new(Vertex_Mix.inputs[2], vertexNode.outputs["Color"])
    byoMAT.node_tree.links.new(Vertex_Math.inputs[0], Vertex_Mix.outputs["Color"])

    if "ScalarParameterValues" in matJSON:
        for param in matJSON["ScalarParameterValues"]:
            if param["ParameterInfo"]["Name"] == "Mask Blend Power":
                Blend_Power = param["ParameterValue"] * 0.01
            elif param["ParameterInfo"]["Name"] == "Opacity":
                pass
            elif param["ParameterInfo"]["Name"] == "NMINT A":
                pass
            elif param["ParameterInfo"]["Name"] == "NMINT B":
                pass
            elif param["ParameterInfo"]["Name"] == "normal_strength":
                pass
            elif param["ParameterInfo"]["Name"] == "Normal Mask Blend Power":
                pass
            elif param["ParameterInfo"]["Name"] == "Normal Mask Blend Mult":
                pass
            elif param["ParameterInfo"]["Name"] == "Metalness Reflection Intensity Adjustment":
                pass
            elif param["ParameterInfo"]["Name"] == "UVTiling X":
                pass
            elif param["ParameterInfo"]["Name"] == "UVTiling Y":
                pass
            elif param["ParameterInfo"]["Name"] == "UVOffsetMultiplier":
                pass
            elif param["ParameterInfo"]["Name"] == "RefractionDepthBias":
                pass
            elif param["ParameterInfo"]["Name"] == "Low Brightness":
                pass
            elif param["ParameterInfo"]["Name"] == "Min Light Brightness":
                pass
            elif param["ParameterInfo"]["Name"] == "Specular":
                pass
            elif param["ParameterInfo"]["Name"] == "Specular Lighting Mult":
                pass
            elif param["ParameterInfo"]["Name"] == "Speed X":
                pass
            elif param["ParameterInfo"]["Name"] == "Speed Y":
                pass
            elif param["ParameterInfo"]["Name"] == "U Tile":
                pass
            elif param["ParameterInfo"]["Name"] == "V Tile":
                pass
            elif param["ParameterInfo"]["Name"] == "UV Scale":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness Mult" or param["ParameterInfo"]["Name"] == "Roughness mult":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness Min" or param["ParameterInfo"]["Name"] == "Roughness_min":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness Max" or param["ParameterInfo"]["Name"] == "Roughness_max":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness A Mult":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness B Mult":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness A Min":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness A Max":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness B Min":
                pass
            elif param["ParameterInfo"]["Name"] == "Roughness B Max":
                pass
            else:
                pass
                # logger.warning(f"Found an unset ScalarParameterValue: {param['ParameterInfo']['Name']}")

    if "TextureParameterValues" in matJSON:
        imgNodePositionY = 700.0
        imgNodeMargin = 300.0
        for texPROP in matJSON["TextureParameterValues"]:
            textImageNode = byoMAT.node_tree.nodes.new('ShaderNodeTexImage')
            texGamePath = os.path.splitext(texPROP["ParameterValue"]["OuterIndex"]["ObjectName"])[0].strip("/")
            # logger.info(texGamePath)
            texPath = CWD.joinpath("export", texGamePath).__str__() + ".tga"
            if Path(texPath).exists():
                textImageNode.image = bpy.data.images.load(texPath)

                # Set Image Node's Label, this helps a lot!
                textImageNode.label = texPROP["ParameterInfo"]["Name"]

                textImageNode.location.x = imgNodePositionX
                textImageNode.location.y = imgNodePositionY

                imgNodePositionY = imgNodePositionY - imgNodeMargin

                if texPROP["ParameterInfo"]["Name"] == "Diffuse":
                    textImageNode.image.alpha_mode = "CHANNEL_PACKED"
                    Diffuse_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Diffuse A":
                    textImageNode.image.alpha_mode = "CHANNEL_PACKED"
                    Diffuse_A_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Diffuse B":
                    textImageNode.image.alpha_mode = "CHANNEL_PACKED"
                    Diffuse_B_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Diffuse B Low":
                    textImageNode.image.alpha_mode = "CHANNEL_PACKED"
                    Diffuse_B_Low_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "MRA":
                    textImageNode.image.colorspace_settings.name = "Linear"
                    MRA_MAP = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "MRA A":
                    textImageNode.image.colorspace_settings.name = "Linear"
                    MRA_MAP = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "MRA B":
                    textImageNode.image.colorspace_settings.name = "Linear"
                    MRA_MAP_B = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "RGBA":
                    textImageNode.image.colorspace_settings.name = "Linear"
                    RGBA_MAP = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Mask Textuer":
                    textImageNode.image.colorspace_settings.name = "Linear"
                    MASK_MAP = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Normal":
                    textImageNode.image.colorspace_settings.name = "Non-Color"
                    Normal_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Texture A Normal":
                    textImageNode.image.colorspace_settings.name = "Non-Color"
                    Normal_A_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "Texture B Normal":
                    textImageNode.image.colorspace_settings.name = "Non-Color"
                    Normal_B_Map = textImageNode

                elif texPROP["ParameterInfo"]["Name"] == "texture":
                    textImageNode.image.colorspace_settings.name = "Linear"
                    P_texture = textImageNode

                else:
                    pass
                    # logger.warning(f"Found an unset TextureParameterValue: {param['ParameterInfo']['Name']}")

    if "VectorParameterValues" in matJSON:
        for param in matJSON["VectorParameterValues"]:
            if param["ParameterInfo"]["Name"] == "DiffuseColor":
                Diffuse_Color.outputs[0].default_value = getRGB(param)
                Diffuse_Color.use_custom_color = True
                Diffuse_Color.color = usedColor
            elif param["ParameterInfo"]["Name"] == "Layer A Tint":
                Layer_A_Tint.outputs[0].default_value = getRGB(param)
                Layer_A_Tint.use_custom_color = True
                Layer_A_Tint.color = usedColor
            elif param["ParameterInfo"]["Name"] == "Layer B Tint":
                Layer_B_Tint.outputs[0].default_value = getRGB(param)
                Layer_B_Tint.use_custom_color = True
                Layer_B_Tint.color = usedColor
            elif param["ParameterInfo"]["Name"] == "AO color":
                AO_Color.outputs[0].default_value = getRGB(param)
                AO_Color.use_custom_color = True
                AO_Color.color = usedColor
            elif param["ParameterInfo"]["Name"] == "Emissive Mult":
                Emissive_Mult.outputs[0].default_value = getRGB(param)
                Emissive_Mult.use_custom_color = True
                Emissive_Mult.color = usedColor
            elif param["ParameterInfo"]["Name"] == "Emissive Color":
                Emissive_Color.outputs[0].default_value = getRGB(param)
                Emissive_Color.use_custom_color = True
                Emissive_Color.color = usedColor
            elif param["ParameterInfo"]["Name"] == "Min Light Brightness Color":
                ML_Brightness.outputs[0].default_value = getRGB(param)
                ML_Brightness.use_custom_color = True
                ML_Brightness.color = usedColor
            elif param["ParameterInfo"]["Name"] == "Lightmass-only Vertex Color":
                LM_Vertex_Color.outputs[0].default_value = getRGB(param)
                LM_Vertex_Color.use_custom_color = True
                LM_Vertex_Color.color = usedColor
            elif param["ParameterInfo"]["Name"] == "color":
                GM_color.outputs[0].default_value = getRGB(param)
                GM_color.use_custom_color = True
                GM_color.color = usedColor

            else:
                # pass
                logger.warning(f"Found an unset VectorParameterValue: {param['ParameterInfo']['Name']}")

    if "BasePropertyOverrides" in matJSON:
        if "ShadingModel" in matJSON["BasePropertyOverrides"]:
            if "MSM_Unlit" in matJSON["BasePropertyOverrides"]["ShadingModel"]:
                isEmissive = True

        if "BlendMode" in matJSON["BasePropertyOverrides"]:
            blendMode = matJSON["BasePropertyOverrides"]["BlendMode"]
            if "BLEND_Translucent" in blendMode or "BLEND_Masked" in blendMode:
                usesAlpha = "CLIP"
                byoMAT.blend_method = "CLIP"
                # byoMAT.blend_method = "CLIP"
            if "BLEND_Additive" in blendMode:
                isAdditive = True

        if "OpacityMaskClipValue" in matJSON["BasePropertyOverrides"]:
            Diffuse_Alpha_Threshold = float(
                matJSON["BasePropertyOverrides"]["OpacityMaskClipValue"])
            byoMAT.alpha_threshold = Diffuse_Alpha_Threshold

    if "StaticParameters" in matJSON:
        if "StaticSwitchParameters" in matJSON["StaticParameters"]:
            for param in matJSON["StaticParameters"]["StaticSwitchParameters"]:
                if param["ParameterInfo"]["Name"] == "Use 2 Diffuse Maps":
                    pass
                if param["ParameterInfo"]["Name"] == "Blend To Flat":
                    pass
                if param["ParameterInfo"]["Name"] == "Blend To Flat MRA":
                    # logger.info("fdasasnodnsafıdsaonfdsaıjkofğdpabfjsdaofbdsajofdsağbfdsao")
                    MRA_blendToFlat = True
                if param["ParameterInfo"]["Name"] == "Blend Roughness":
                    pass
                if param["ParameterInfo"]["Name"] == "Use Vertex Color":
                    USE_VERTEX_COLOR = True

    # if "StaticParameters" in matJSON:
    #     if "StaticComponentMaskParameters" in matJSON:
    #         for param in matJSON["StaticParameters"]["StaticComponentMaskParameters"]:
    #             if param["ParameterInfo"]["Name"] == "Mask":
    #                 if param["R"]:
    #                     RGBA_MASK_COLOR = "R"
    #                 if param["G"]:
    #                     RGBA_MASK_COLOR = "G"
    #                 if param["B"]:
    #                     RGBA_MASK_COLOR = "B"
    #             if param["ParameterInfo"]["Name"] == "Use Vertex Color":
    #                 USE_VERTEX_COLOR = True
    #             else:
    #                 logger.warning(f"Found an unset VectorParameterValue: {param['ParameterInfo']['Name']}")

    # // ------------------------------------------------------------------------

    if MRA_MAP:

        sepRGB_MRA_node = createNode(material=byoMAT, lookFor="", nodeName="ShaderNodeSeparateRGB", label="Seperate RGB_MRA", pos=[MRA_MAP.location.x + 300, MRA_MAP.location.y])
        byoMAT.node_tree.links.new(sepRGB_MRA_node.inputs['Image'], MRA_MAP.outputs["Color"])

        # byoMAT.node_tree.links.new(bsdf.inputs['Metallic'], sepRGB_MRA_node.outputs["R"])
        byoMAT.node_tree.links.new(bsdf.inputs['Roughness'], sepRGB_MRA_node.outputs["G"])
        byoMAT.node_tree.links.new(bsdf.inputs['Alpha'], sepRGB_MRA_node.outputs["B"])

        if MRA_blendToFlat:
            byoMAT.node_tree.links.new(sepRGB_MRA_node.inputs['Image'], MRA_MAP.outputs["Color"])
            if MRA_blendToFlat:
                # logger.warning("yoyoyoyo")
                MRA_MIX = createNode(material=byoMAT, lookFor="asd", nodeName="ShaderNodeMixRGB", label="mix MRA", pos=[MRA_MAP.location.x + 500, MRA_MAP.location.y - 150])
                byoMAT.node_tree.links.new(MRA_MIX.inputs[0], vertexNode.outputs["Color"])
                byoMAT.node_tree.links.new(MRA_MIX.inputs['Color1'], MRA_MAP.outputs["Color"])
                MRA_MIX.inputs["Color2"].default_value = BLACK_RGB

                byoMAT.node_tree.links.new(sepRGB_MRA_node.inputs['Image'], MRA_MIX.outputs["Color"])
                byoMAT.node_tree.links.new(bsdf.inputs['Roughness'], sepRGB_MRA_node.outputs["G"])
            else:
                # byoMAT.node_tree.links.new(bsdf.inputs['Metallic'], sepRGB_MRA_M_node.outputs["R"])
                byoMAT.node_tree.links.new(bsdf.inputs['Roughness'], sepRGB_MRA_node.outputs["G"])
                # byoMAT.node_tree.links.new(bsdf.inputs['Alpha'], sepRGB_MRA_M_node.outputs["B"])

    if Diffuse_Map:

        # Layer_Z_Diffuse_Tint_Mix

        if Diffuse_Color.use_custom_color:
            byoMAT.node_tree.links.new(Layer_Z_Diffuse_Tint_Mix.inputs[1], Diffuse_Map.outputs["Color"])
            byoMAT.node_tree.links.new(Layer_Z_Diffuse_Tint_Mix.inputs[2], Diffuse_Color.outputs["Color"])
            byoMAT.node_tree.links.new(bsdf.inputs['Base Color'], Layer_Z_Diffuse_Tint_Mix.outputs["Color"])
        else:
            byoMAT.node_tree.links.new(bsdf.inputs['Base Color'], Diffuse_Map.outputs["Color"])
        if usesAlpha:
            byoMAT.node_tree.links.new(bsdf.inputs["Alpha"], Diffuse_Map.outputs["Alpha"])

        if USE_VERTEX_COLOR:
            byoMAT.node_tree.links.new(Layer_Z_Diffuse_Tint_Mix.inputs[2], LM_Vertex_Color.outputs["Color"])
            byoMAT.node_tree.links.new(Layer_Z_Diffuse_Tint_Mix.inputs[1], Diffuse_Map.outputs["Color"])

    # ANCHOR Work here -------------
    if Diffuse_A_Map:

        byoMAT.node_tree.links.new(Vertex_Mix.inputs[1], Diffuse_A_Map.outputs["Alpha"])
        # Set Materials Diffuse to DiffuseMix Node
        byoMAT.node_tree.links.new(bsdf.inputs['Base Color'], Diffuse_Mix.outputs["Color"])

        # DiffuseColorMix Node
        # Pass Vertex Data
        byoMAT.node_tree.links.new(Diffuse_Mix.inputs[0], Vertex_Math.outputs[0])
        byoMAT.node_tree.links.new(Diffuse_Mix.inputs[1], Layer_A_Diffuse_Tint_Mix.outputs["Color"])        # Pass Layer 1
        byoMAT.node_tree.links.new(Diffuse_Mix.inputs[2], Layer_B_Diffuse_Tint_Mix.outputs["Color"])        # Pass Layer 2

        # Layer_A_Diffuse_Tint_Mix Node
        byoMAT.node_tree.links.new(Layer_A_Diffuse_Tint_Mix.inputs[1], Layer_A_Tint.outputs["Color"])
        byoMAT.node_tree.links.new(Layer_A_Diffuse_Tint_Mix.inputs[2], Diffuse_A_Map.outputs["Color"])

        # Layer_B_Diffuse_Tint_Mix Node
        byoMAT.node_tree.links.new(Layer_B_Diffuse_Tint_Mix.inputs[1], Layer_B_Tint.outputs["Color"])
        if Diffuse_B_Map:
            byoMAT.node_tree.links.new(Layer_B_Diffuse_Tint_Mix.inputs[2], Diffuse_B_Map.outputs["Color"])
        else:
            Layer_B_Diffuse_Tint_Mix.inputs[1].default_value = WHITE_RGB

        Layer_A_Diffuse_Tint_Mix.inputs[0].default_value = 1
        Layer_B_Diffuse_Tint_Mix.inputs[0].default_value = 1
        Layer_A_Diffuse_Tint_Mix.blend_type = "MULTIPLY"
        Layer_B_Diffuse_Tint_Mix.blend_type = "MULTIPLY"

    if Normal_Map:
        byoMAT.node_tree.links.new(normalNode.inputs["Color"], Normal_Map.outputs["Color"])
        byoMAT.node_tree.links.new(bsdf.inputs['Normal'], normalNode.outputs['Normal'])

    if Normal_A_Map:
        byoMAT.node_tree.links.new(Normal_Mix.inputs[0], Vertex_Math.outputs[0])
        byoMAT.node_tree.links.new(Normal_Mix.inputs[1], Normal_A_Map.outputs["Color"])

        if Normal_B_Map:
            byoMAT.node_tree.links.new(Normal_Mix.inputs[2], Normal_B_Map.outputs["Color"])
        else:
            Normal_Mix.inputs[1].default_value = WHITE_RGB

        byoMAT.node_tree.links.new(normalNode.inputs["Color"], Normal_Mix.outputs["Color"])
        byoMAT.node_tree.links.new(bsdf.inputs['Normal'], normalNode.outputs['Normal'])

    if RGBA_MAP:
        sepRGB_RGBA_node = createNode(material=byoMAT, lookFor="", nodeName="ShaderNodeSeparateRGB", label="Seperate RGB_RGBA", pos=[-390.0, -200])
        byoMAT.node_tree.links.new(sepRGB_RGBA_node.inputs[0], RGBA_MAP.outputs["Color"])
        byoMAT.node_tree.links.new(bsdf.inputs["Alpha"], sepRGB_RGBA_node.outputs[RGBA_MASK_COLOR])

    if P_texture:
        byoMAT.node_tree.links.new(bsdf.inputs['Base Color'], P_texture.outputs["Color"])
        byoMAT.node_tree.links.new(bsdf.inputs["Alpha"], P_texture.outputs["Color"])

        if isAdditive:
            byoMAT.node_tree.links.new(bsdf.inputs["Emission"], P_texture.outputs["Color"])
            # pass


def setMaterials(byo: bpy.types.Object, objectName: str, objectPath: str, object_OG: dict, object: dict, objIndex: int, JSON_Folder: Path):
    # logger.info(f"setMaterials() | Object : {byo.name_full}")

    objectProperties = object["ExportValue"]
    objectProperties_OG = object_OG["Exports"][2]["ExportValue"]
    matFolder = JSON_Folder.joinpath("Materials")
    matFolder.mkdir(exist_ok=True)

    # saveJSON(p=JSON_Folder.joinpath(objectName + "_OG" + ".json"), d=object_OG)

    if "StaticMaterials" in objectProperties_OG:
        for index, mat in enumerate(objectProperties_OG["StaticMaterials"]):
            if type(mat["MaterialInterface"]) is dict:
                matName = getMatName(mat["MaterialInterface"])
                # matName = mat["ImportedMaterialSlotName"]
                if "WorldGridMaterial" not in matName:

                    matPath = getMatPath(mat["MaterialInterface"])
                    matPack = provider.get_package(matPath)
                    if matPack is not None:
                        matJSON_FULL = matPack.parse_package().get_dict()
                        if _DEBUG:
                            saveJSON(p=matFolder.joinpath(matName + "_OG" + ".json"), d=matJSON_FULL)
                        try:
                            byoMAT = byo.material_slots[index].material
                            byoMAT.name = matName
                            setMaterial(byoMAT=byoMAT, matJSON_FULL=matJSON_FULL, override=False)
                        except IndexError:
                            pass

    if "OverrideMaterials" in objectProperties:
        for index, mat in enumerate(objectProperties["OverrideMaterials"]):
            if type(mat) is dict:
                matPath = getMatPath(mat)
                matPack = provider.get_package(matPath)
                matJSON_FULL = matPack.parse_package().get_dict()

                matJSON = matJSON_FULL["Exports"][0]["ExportValue"]
                matName = matJSON_FULL["Exports"][0]["ExportName"]

                # REVIEW
                if _DEBUG:
                    saveJSON(p=matFolder.joinpath(matName + "_OVR" + ".json"), d=matJSON_FULL)

                try:
                    byoMAT = byo.material_slots[index].material
                    byoMAT.name = matName
                    # logger.info(f"[{objIndex}] : Setting Material (Override) : {matName}")
                    setMaterial(byoMAT=byoMAT, matJSON_FULL=matJSON_FULL, override=True)
                except IndexError:
                    pass


def importObject(object, objectIndex, umapName, mainScene):
    # logger.info(object)
    objectProperties = object["ExportValue"]
    objName = getObjectname(objectProperties)
    objPath = getFixedPath(objectProperties) + ".gltf"
    # objProp = readPROP(getFixedPath(objectProperties))

    crt_JSON_FOLDER = JSON_FOLDER.joinpath(umapName, objName)
    crt_JSON_FOLDER.mkdir(parents=True, exist_ok=True)
    if _DEBUG:
        saveJSON(p=crt_JSON_FOLDER.joinpath(objName + ".json"), d=objectProperties)

    if Path(objPath).exists():
        logger.info(f"[{objectIndex}] : Importing GLTF : {objPath}")
        with redirect_stdout(stdout):
            bpy.ops.import_scene.gltf(filepath=objPath, loglevel=5, merge_vertices=True)

        imported = bpy.context.active_object

        blenderUtils.objectSetProperties(imported, objectProperties)

        objGamePath = getObjectPath(objectProperties)

        # "/Engine/BasicShapes/Plane"
        # "Engine/Content/BasicShapes/Plane"
        if "/Engine/" in objGamePath:
            objGamePath = objGamePath.replace("/Engine/", "Engine/Content/")

        objPack = provider.get_package(objGamePath)
        objJSON_OG = objPack.parse_package().get_dict()

        if _DEBUG:
            saveJSON(p=crt_JSON_FOLDER.joinpath(objName + "_OG" + ".json"), d=objJSON_OG)
        setMaterials(byo=imported, objectName=objName, objectPath=objPath, object_OG=objJSON_OG, object=object, objIndex=objectIndex, JSON_Folder=crt_JSON_FOLDER)

        # Move Object to UMAP Collection
        bpy.data.collections[umapName].objects.link(imported)
        mainScene.collection.objects.unlink(imported)

    else:
        logger.warning(f"Couldn't find Found GLTF : {objPath}")


def createLight(object: dict, index: int, collectionName: str, lightType: str = "POINT"):

    light_data = bpy.data.lights.new(name="", type=lightType)
    light_data.energy = 1000

    if lightType == "AREA":
        light_data.shape = "RECTANGLE"
        if "SourceWidth" in object["ExportValue"]:
            light_data.size = object["ExportValue"]["SourceWidth"] * 0.01
        if "SourceHeight" in object["ExportValue"]:
            light_data.size_y = object["ExportValue"]["SourceHeight"] * 0.01

    if lightType == "SPOT":
        if "OuterConeAngle" in object["ExportValue"]:
            light_data.spot_size = radians(object["ExportValue"]["OuterConeAngle"])

    # NOTE
    # Check these?
    #   "SourceRadius": 38.2382,
    #   "AttenuationRadius": 840.22626

    if "Intensity" in object["ExportValue"]:
        if "Intensity" in object["ExportValue"]:
            light_data.energy = object["ExportValue"]["Intensity"] * 0.1

    if "LightColor" in object["ExportValue"]:
        if "LightColor" in object["ExportValue"]:
            light_data.color = [
                abs((object["ExportValue"]["LightColor"]["R"]) / float(255)),
                abs((object["ExportValue"]["LightColor"]["G"]) / float(255)),
                abs((object["ExportValue"]["LightColor"]["B"]) / float(255))
            ]

    light_object = bpy.data.objects.new(name=object["ExportName"], object_data=light_data)

    blenderUtils.objectSetProperties(light_object, object["ExportValue"])
    bpy.data.collections[collectionName].objects.link(light_object)


@timer
def main():
    cacheCheck()

    global provider
    provider = UE4Parser(VAL_PAKS_PATH, VAL_KEY)

    # Set renderer to Cycles so Eeeve doesn't scream.
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'

    # # # // --------------------------------------------------
    # # # Blender Loop

    MAP_FOLDER = CWD.joinpath("export", "Maps", SELECTED_MAP.capitalize())
    MAP_FOLDER.mkdir(parents=True, exist_ok=True)

    for umapIndex, umap in enumerate(_umapList.MAPS[SELECTED_MAP.lower()]):
        blenderUtils.cleanUP()

        umapFolderName = umap.split("_", 1)[0]
        umapName = os.path.splitext(os.path.basename(umap))[0]
        umapPKG = provider.get_package(umap)
        logger.info(f"Processing UMAP : {umapName}")

        if "Lighting" in umapName:
            if umapPKG is not None:
                # Use the data directly, because why not.
                umapDATA_FULL = umapPKG.parse_package().get_dict()
                umapDATA = umapDATA_FULL["Exports"]

                # Save for debug purposes, has no use.
                if _DEBUG:
                    saveJSON(p=MAP_FOLDER.joinpath(umapName + ".json"), d=umapDATA_FULL)

                main_scene = bpy.data.scenes["Scene"]

                import_collection = bpy.data.collections.new(umapName)
                main_scene.collection.children.link(import_collection)

                logger.info(f"Processing UMAP : {umapName}")

                point_lights = bpy.data.collections.new("Point Lights")
                rect_lights = bpy.data.collections.new("Rect Lights")
                spot_lights = bpy.data.collections.new("Spot Lights")

                import_collection.children.link(point_lights)
                import_collection.children.link(rect_lights)
                import_collection.children.link(spot_lights)

                for objectIndex, object in enumerate(umapDATA):

                    if object["ExportType"] == "PointLightComponent":
                        createLight(object=object, index=objectIndex, collectionName="Point Lights", lightType="POINT")

                    if object["ExportType"] == "RectLightComponent":
                        createLight(object=object, index=objectIndex, collectionName="Rect Lights", lightType="AREA")

                    if object["ExportType"] == "SpotLightComponent":
                        createLight(object=object, index=objectIndex, collectionName="Spot Lights", lightType="SPOT")

                bpy.ops.wm.save_as_mainfile(filepath=CWD.joinpath("export", "Scenes", umapName).__str__() + ".blend")

        elif "VFX" in umapName:
            pass

        else:
            if umapPKG is not None:
                # Use the data directly, because why not.

                umapDATA_FULL = umapPKG.parse_package().get_dict()
                umapDATA = umapDATA_FULL["Exports"]

                # Save for debug purposes, has no use.
                if _DEBUG:
                    saveJSON(p=MAP_FOLDER.joinpath(umapName + ".json"), d=umapDATA_FULL)

                main_scene = bpy.data.scenes["Scene"]

                import_collection = bpy.data.collections.new(umapName)
                main_scene.collection.children.link(import_collection)

                logger.info(f"Processing UMAP : {umapName}")

                for objectIndex, object in enumerate(umapDATA):
                    if checkImportable(object):
                        importObject(object, objectIndex, umapName, main_scene)

            # ! Utility to pack
            # bpy.ops.file.pack_all()

            # ! Save umap to .blend file
            bpy.ops.wm.save_as_mainfile(filepath=CWD.joinpath("export", "Scenes", umapName).__str__() + ".blend")

    # ! Clear everything
    blenderUtils.cleanUP()
    # ! Save umap to .blend file
    bpy.ops.wm.save_as_mainfile(filepath=CWD.joinpath("export", "Scenes", SELECTED_MAP.capitalize()).__str__() + ".blend")

    # ! Import other .blend files back!
    for umap in _umapList.MAPS[SELECTED_MAP]:
        umapName = os.path.splitext(os.path.basename(umap))[0]
        umapBlend = CWD.joinpath("export", "Scenes", umapName).__str__() + ".blend"

        sec = "\\Collection\\"
        obj = umapName

        fp = umapBlend + sec + obj
        dr = umapBlend + sec

        if Path(umapBlend).exists():

            if _APPEND:
                bpy.ops.wm.append(filepath=fp, filename=obj, directory=dr)
            else:
                bpy.ops.wm.link(filepath=fp, filename=obj, directory=dr)

    # ANCHOR
    # Set up Skybox
    # This is so junky omfg.
    bpy.context.scene.render.film_transparent = True
    worldMat = bpy.data.worlds['World']
    worldNodeTree = worldMat.node_tree

    # ANCHOR
    # Set up Skybox
    # This is so junky omfg.
    bpy.context.scene.render.film_transparent = True
    worldMat = bpy.data.worlds['World']
    worldNodeTree = worldMat.node_tree

    if SELECTED_MAP.lower() == "ascent":
        skyboxMapPath = r"export\Game\Environment\Asset\WorldMaterials\Skybox\M0\Skybox_M0_VeniceSky_DF.tga"
    elif SELECTED_MAP.lower() == "split":
        skyboxMapPath = r"export\Game\Environment\Bonsai\Asset\Props\Skybox\0\M0\Skybox_0_M0_DF.tga"
    elif SELECTED_MAP.lower() == "bind":
        # NOTE bind skybox is ugly as fuck! So I used
        # skyboxMapPath = r"export\Game\Environment\Asset\WorldMaterials\Skybox\M0\Skybox_M0_DualitySky_DF.tga"
        skyboxMapPath = r"export\Game\Environment\Asset\WorldMaterials\Skybox\M0\Skybox_M0_VeniceSky_DF.tga"
    elif SELECTED_MAP.lower() == "icebox":
        skyboxMapPath = r"export\Game\Environment\Port\WorldMaterials\Skydome\M1\Skydome_M1_DF.tga"
    elif SELECTED_MAP.lower() == "breeze":
        skyboxMapPath = r"export\Game\Environment\FoxTrot\Asset\Props\Skybox\0\M0\Skybox_0_M0_DF.tga"
    elif SELECTED_MAP.lower() == "haven":
        skyboxMapPath = r"export\Game\Environment\Asset\WorldMaterials\Skybox\M3\Skybox_M3_DF.tga"
    elif SELECTED_MAP.lower() == "menu":
        skyboxMapPath = r"export\Game\Environment\Port\WorldMaterials\Skydome\M1\Skydome_M1_DF.tga"
    elif SELECTED_MAP.lower() == "poveglia":
        skyboxMapPath = r"export\Game\Environment\Port\WorldMaterials\Skydome\M1\Skydome_M1_DF.tga"
    else:
        skyboxMapPath = r"export\Game\Environment\Asset\WorldMaterials\Skybox\M0\Skybox_M0_VeniceSky_DF.tga"

    ENV_MAP = os.path.join(CWD.__str__(), skyboxMapPath)

    ENV_MAP_NODE = createNode(worldMat, lookFor="Environment Texture", nodeName="ShaderNodeTexEnvironment", label="SkyboxTexture_VALORANT")
    ENV_MAP_NODE.image = bpy.data.images.load(ENV_MAP)

    BG_NODE = worldNodeTree.nodes["Background"]
    BG_NODE.inputs["Strength"].default_value = 3

    worldNodeTree.links.new(worldNodeTree.nodes["Background"].inputs['Color'], ENV_MAP_NODE.outputs["Color"])
    worldNodeTree.links.new(worldNodeTree.nodes['World Output'].inputs['Surface'], worldNodeTree.nodes["Background"].outputs["Background"])

    # ! Save umap to .blend file
    bpy.ops.wm.save_as_mainfile(filepath=CWD.joinpath("export", "Scenes", SELECTED_MAP.capitalize()).__str__() + ".blend")


if (2, 93, 0) > bpy.app.version:
    logger.warning(
        "Your version of Blender is not supported, update to 2.93 or higher.")
    logger.warning("https://www.blender.org/download/")
else:
    GLTF_ENABLED = addon_utils.check('io_scene_gltf2')[0]
    if not GLTF_ENABLED:
        addon_utils.enable("io_scene_gltf2", default_set=True)
        logger.info("Enabled : GLTF Addon!")

    main()
