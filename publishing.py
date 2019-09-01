import os
import arcpy
from arcgis.gis import GIS

default_proj_path = r'O:\01 Land & Property Info\Updating Parcel & Property Layers\Updating Parcel & Property Layers.aprx'

def publishLayer(map_name, layer_name, shr_everyone=True, prj_path= default_proj_path):

    portal = "http://www.arcgis.com"
    user = "####"
    password = "####"

    # Set sharing options
    shr_org = True
    shr_groups = ""

    # Local paths to create temporary content
    loc_path = r'O:\01 Land & Property Info\Updating Parcel & Property Layers'
    sd_draft = os.path.join(loc_path, layer_name + '.sddraft')
    sd = os.path.join(loc_path, layer_name + '.sd')

    # Create a new SDDraft and stage to SD
    print("Creating SD draft")
    arcpy.env.overwriteOutput = True
    prj = arcpy.mp.ArcGISProject(prj_path)
    mp = prj.listMaps(map_name)[0]
    arcpy.mp.CreateWebLayerSDDraft(mp, sd_draft, layer_name, 'MY_HOSTED_SERVICES', 'FEATURE_ACCESS', '', True, True)
    print("SD draft created")
    print("Creating SD")
    arcpy.StageService_server(sd_draft, sd)
    print("SD created")

    print("Connecting to {}".format(portal))
    gis = GIS(portal, user, password)

    # Find the SD, update it, publish w/ overwrite and set sharing and metadata
    print("Search for original SD on portal…")
    # Check that the correct layer has been found
    match = 0
    layer_number = 0
    while match == 0:
        sd_item = gis.content.search("title:{} AND owner:{}".format(layer_name, user),
                                     item_type="Service Definition")[layer_number]
        found_layer = sd_item.title
        if found_layer == layer_name:
            match = 1
        else:
            layer_number = layer_number + 1
    print("Found SD: {}, ID: {} - Uploading and overwriting…".format(sd_item.title, sd_item.id))
    # Update the service definition and overwrite the hosted layer
    sd_item.update(data=sd)
    print("Overwriting existing feature service…")
    fs = sd_item.publish(overwrite=True)

    if shr_org or shr_everyone or shr_groups:
        print("Setting sharing options…")
    fs.share(org=shr_org, everyone=shr_everyone, groups=shr_groups)
    print("Finished updating: {} – ID: {}".format(fs.title, fs.id))