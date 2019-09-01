# This script updates the local copies of several feature classes, and publishes them to ArcGIS Online.
# It should be run weekly (typically Monday morning) to keep council GIS services up to date with the data published
# in the LINZ Data Service.
#
# Author: Tim White - tim.white@qldc.govt.nz
# Last update: 10/6/19

import arcpy
import os
import shutil
import time
import publishing
start = time.time()

# The existing GDB is first moved to a backup folder on C:\Temp, for the sake of having last week's copy if needed.
# This includes the LINZ layers, and the layers involved in creating the Parcel Property feature class


linz_gdb_src = r'O:\01 Land & Property Info\Update LINZ Data using ArcGIS Pro\LINZ_DS_Layers.gdb'
changeset_gdb_src = r'O:\01 Land & Property Info\Update LINZ Data using ArcGIS Pro\LINZ_Parcel_Changeset.gdb'
linz_dst = r'C:\Temp\BACKUP\LINZ_DS_Layers.gdb'
changeset_dst = r'C:\Temp\BACKUP\LINZ_Parcel_Changeset.gdb'
temp_folder = r'C:\Users\timwh\AppData\Local\Temp'
temp_files = os.listdir(temp_folder)

# The DataInteroperability extension is a separate license, and is required for running the FME model
if arcpy.CheckExtension('DataInteroperability') == 'Available':
    pass
else:
    print('Data Interopability extension is unavailable - script will not proceed')
    quit()

try:
    shutil.rmtree(linz_dst)
    shutil.copytree(linz_gdb_src, linz_dst)
except WindowsError as e:
    print(e)
    print('Warning! LINZ layers GDB not moved to backup successfully!')
else:
    shutil.rmtree(linz_gdb_src)
    print('LINZ layers GDB backed up')

try:
    shutil.rmtree(changeset_dst)
    shutil.copytree(changeset_gdb_src, changeset_dst)
except WindowsError as e:
    print(e)
    print('Warning! Changeset GDB not moved to backup successfully!')
else:
    shutil.rmtree(changeset_gdb_src)
    print('Changeset GDB backed up')


# The FME model was imported into an ArcGIS toolbox as a spatial ETL model
arcpy.ClearEnvironment('workspace')
arcpy.ClearEnvironment('scratchWorkspace')
ws = r'O:\01 Land & Property Info\Updating Parcel & Property Layers\Updating Parcel & Property Layers.gdb'
arcpy.env.workspace = ws
arcpy.env.scratchWorkspace = ws
tbx = (r'O:\01 Land & Property Info\Updating Parcel & Property Layers\ParcelPropTBX.tbx')
arcpy.ImportToolbox(tbx)

# The DataInteroperability extension is a separate license, and is required for running the FME model
attempt = 1
while attempt in range(5):
    arcpy.CheckOutExtension('DataInteroperability')
    print('Checked out \"DataInteroperability\" Extension')
    print('Downloading data from LINZ and writing to new geodatabase...')
# Run LINZ Layer Updater FME Model
    try:
        arcpy.ParcelPropTBX.LINZLayerUpdater()
    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        attempt += 1
        if attempt == 4:
            print('FME tool refuses to run. Script will not proceed')
            arcpy.CheckInExtension('DataInteroperability')
            quit()
    else:
        print('LINZ Layers GDB Updated')
        arcpy.CheckInExtension('DataInteroperability')
        print('Checked in \"DataInteroperability\" Extension')
        break

vector = r'O:\01 Land & Property Info\Updating Parcel & Property Layers\GIS_Vector.sde\GIS_VECTOR.SDE.'
linz_gdb = r'O:\01 Land & Property Info\Update LINZ Data using ArcGIS Pro\LINZ_DS_Layers.gdb'
boundary = vector + 'QLDC_BOUNDARY'
parcel_cp = vector + 'Parcel_CurrentPrimary'
t1_view = vector + 'vw_T1_QMapsProperty'
parcel = linz_gdb + r'\\' + 'Parcel'
parcel_joined = parcel + '_joined'
t1_view_local = linz_gdb + r'\\' + 'vw_T1_QMapsProperty'
no_id_match = linz_gdb + r'\\' + 'No_ID_Match'
parcel_property = linz_gdb + r'\\' + "Parcel_Property"

arcpy.env.workspace = linz_gdb
arcpy.env.overwriteOutput = True

# The following code creates the ParcelProperty layer by means of various geoprocesses. It's commented a bit more
# heavily than necessary, for the sake of quickly and easily finding the processes to make required changes. The
# original models that the following process is based on are inside the toolbox (path assigned to the variable 'tbx').

# Delete parcels outside district from the gdb layers
print("Removing parcels outside the district...")
for fc in arcpy.ListFeatureClasses():
    desc = arcpy.Describe(fc)
    if desc.name != 'Road':
        select = arcpy.SelectLayerByLocation_management(linz_gdb + r"\\" + fc, 'INTERSECT',
                                                    invert_spatial_relationship=True)
        arcpy.DeleteRows_management(select)
print('Layers limited to district')

# Empty the Parcel_CurrentPrimary layer in Vector
print("Updating Parcel_CurrentPrimary...")
arcpy.DeleteRows_management(parcel_cp)

# Add the features from the parcel layer that are current/approved and primary to Parcel_CurrentPrimary layer in Vector
# This specific feature class is referenced by an SQL view that creates the join with T1 data
parcel_query = "(status = 'Current' Or status = 'Approved as to Survey') And (topology_type = 'Primary') AND (parcel_intent <> 'Road')"
parcel_selection = arcpy.SelectLayerByAttribute_management(parcel, where_clause=parcel_query)
arcpy.Append_management(parcel_selection, parcel_cp)
print('Parcel_CurrentPrimary updated')

# Create local copy of vw_T1_QMapsProperty - the view created from the previous feature class
print('Creating local copy of vw_T1_QMapsProperty...')
arcpy.FeatureClassToFeatureClass_conversion(t1_view, linz_gdb, "vw_T1_QMapsProperty")
print('Local copy of T1 data created')

# Remove features with no geometry from local copy of vw_T1_QMapsProperty
print('Removing features with no geometry from local copy of vw_T1_QMapsProperty...')
arcpy.AddGeometryAttributes_management(t1_view_local, 'AREA_GEODESIC', Area_Unit='HECTARES')
no_geometry = arcpy.SelectLayerByAttribute_management(t1_view_local, where_clause='AREA_GEO = 0')
arcpy.DeleteRows_management(no_geometry)
print('Features without geometry deleted')

# Create layers from parcel and view feature classes, join the layers on ID
arcpy.MakeFeatureLayer_management(parcel, 'parcel_layer')
arcpy.MakeFeatureLayer_management(t1_view_local, 't1_view_local_layer')
arcpy.AddJoin_management('parcel_layer', 'id', 't1_view_local_layer', 'parid')
print('Parcel and local view layers created and joined')

# Create no_id_match feature class
print('Creating no match feature class...')
no_match_clause = "vw_T1_QMapsProperty.OBJECTID IS NULL"
no_match = arcpy.SelectLayerByAttribute_management('parcel_layer', where_clause=no_match_clause)
arcpy.RemoveJoin_management('parcel_layer')
arcpy.CopyFeatures_management(no_match, no_id_match)
print('No match feature class created')

# Remove extraneous parcels (status, type, location) from the no_id_match feature class
print('Removing extraneous parcels from the no match feature class...')
no_id_query = "status <> 'Current' Or topology_type <> 'Primary'"
ext_parcels_status = arcpy.SelectLayerByAttribute_management(no_id_match, where_clause=no_id_query)
arcpy.DeleteRows_management(ext_parcels_status)
ext_parcels_loc = arcpy.SelectLayerByLocation_management(no_id_match, 'INTERSECT', boundary,
                                                         invert_spatial_relationship=True)
arcpy.DeleteRows_management(ext_parcels_loc)
print('Extraneous parcels removed')

# Create Parcel and Property feature class
print('Creating Parcel Property layer...')
arcpy.AddField_management(no_id_match, 'PAR_ID', 'LONG')
arcpy.Union_analysis([no_id_match, t1_view_local], parcel_property)
print('Parcel Property layer created')

# Adding fields to Parcels and Property
print('Adding and calculating Parcel Property fields')
arcpy.AddField_management(parcel_property, 'More_Info', 'TEXT')
arcpy.AddField_management(parcel_property, 'Street View', 'TEXT')
arcpy.AddField_management(parcel_property, 'eDocs', 'TEXT')
arcpy.AddField_management(parcel_property, 'iDocs', 'TEXT')

# Functions used to calculate Parcels and Property fields
def street_View(y,x):
    return "http://maps.google.co.nz/maps?f=q&layer=c&cbll={},{}&cbp=12,0,,0,5".format(y, x)

def rates_Link(id):
    return "https://services.qldc.govt.nz/eProperty/P1/eRates/RatingInformation.aspx?r=QLDC.WEB.GUEST&f=%24P1.ERA.RATDETAL.VIW&PropertyNo={}".format(id)

def eDocs_Link(id):
    return "https://edocs.qldc.govt.nz/Search?search={}".format(id)

def iDocs_Link(id):
    return "http://know/Zones/API/ECM/Property?id={}".format(id)


# Calculate Parcel Property fields - Update cursors are apparently quicker than the CalculateField_Management tools
# when a function (codeblock) is required
arcpy.AddGeometryAttributes_management(parcel_property, "CENTROID_INSIDE")
fields = ['PAR_ID', 'parid', 'id', 'TRIM_property_no', 'Prop_ID', 'More_Info', 'Street_View', 'INSIDE_Y',
            'INSIDE_X', 'eDocs', 'iDocs']
with arcpy.da.UpdateCursor(parcel_property, fields) as cursor:
    for row in cursor:
        # Fill PAR_ID field
        if row[1] == 0:
            row[0] = row[2]
        else:
            row[0] = row[1]
        # If TRIM_property_no is empty, make it P0
        if row[3] == '':
            row[3] = 'P0'
        # If Prop_ID is null, set it to 0
        if row[4] is None:
            row[4] = 0
        # Fill the More_Info field with the rates link
        row[5] = rates_Link(row[4])
        # Create the street view link
        row[6] = street_View(row[7], row[8])
        # Create the eDocs link
        row[9] = eDocs_Link(row[4])
        # Create the iDocs link
        row[10] = iDocs_Link(row[4])
        cursor.updateRow(row)

arcpy.MakeFeatureLayer_management(parcel_property, 'parcel_property_layer')
arcpy.AddJoin_management('parcel_property_layer', 'PAR_ID', 'parcel_layer', 'id')
pp_select = arcpy.SelectLayerByAttribute_management('parcel_property_layer', where_clause='Parcel_Property.id = 0')
arcpy.CalculateFields_management(pp_select, "PYTHON3",
                                 [['Parcel_Property.appellation', '!Parcel.appellation!'],
                                  ['Parcel_Property.affected_surveys', '!Parcel.affected_surveys!'],
                                  ['Parcel_Property.parcel_intent', '!Parcel.parcel_intent!'],
                                  ['Parcel_Property.topology_type', '!Parcel.topology_type!'],
                                  ['Parcel_Property.status', '!Parcel.status!'],
                                  ['Parcel_Property.statutory_actions', '!Parcel.statutory_actions!'],
                                  ['Parcel_Property.land_district', '!Parcel.land_district!'],
                                  ['Parcel_Property.titles', '!Parcel.titles!'],
                                  ['Parcel_Property.survey_area', '!Parcel.survey_area!'],
                                  ['Parcel_Property.calc_area', '!Parcel.calc_area!']])
arcpy.RemoveJoin_management('parcel_property_layer')
print('Parcel Property fields added and calculated')


# Call the publishing function for each of the layers that need updating.
publishing.publishLayer('Publishing', 'Crown Land')
publishing.publishLayer('Publishing', 'Owner', False)
publishing.publishLayer('Publishing', 'All Parcels')
publishing.publishLayer('Publishing', 'Roads _Addressing_')
publishing.publishLayer('Publishing', 'Address _Electoral_')
publishing.publishLayer('Publishing', 'Parcels and Property')

print("All layers published. Optimize Parcels_Property in ArcGIS Online and confirm the accurate display - particularly"
       " the labels - of all layers.")

# It's not important to actually delete everything, I'm  just trying to stop the temp folder growing over time,
# as the script adds a few small files each time it's run, hence ignoring any Windows errors.

print('Removing temp files created by the script')
for path in temp_files:
    if os.path.isdir(path):
        try:
            shutil.rmtree(temp_folder + '\\' + path)
        except WindowsError as e:
            pass
    else:
        try:
            os.remove(temp_folder + '\\' + path)
        except WindowsError as e:
            pass

end = time.time()
print('Update process completed in {} minutes'.format(round((end-start)/60), 2))





