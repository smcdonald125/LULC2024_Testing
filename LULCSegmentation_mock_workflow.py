import os 
import sys
import pandas as pd 
import geopandas as gpd 

"""
Mock workflow in arcpy to create LULC change segmentation.
1. Create T3 psegs with T3_SID and T3_LC
2. Use the 2 change periods to create T1_SID and T1_LC, T2_SID and T2_LC.
3. Union T3 psegs, T1 and T2 segments where change occured.
    - This will inherently union by parcel due to psegs
    - This will make change crosswalkable with T3 psegs by PSID and T3_SID
4. In 2022 ed., change database required segmentation by wetlands type.
    - Can this be handled in burn in like T3 to avoid additional segmentation?
"""

def assign_change(df, t):
    """
    assign_change take change segments, select those with change, classify the early date LC and assign SID.

    Parameters
    ----------
    df : [GeoPandas GeoDataframe]
        gdf of change segments. Wall-to-wall of change and no change.
    t : [str]
        time period to name column (T1 or T2)
    """
    # new columns
    sid = f"{t}_SID"
    lc_col = f"{t}_LC"

    # subset to needed cols
    df = df[['Class_name','geometry']]

    # read in crosswalk
    cw = pd.read_csv(r"C:/Users/smcdonald/Documents/Code/LandUse_V2/Version2/documentation/lc_chg_classes_v2_cbw.csv")
    t = cw['Description'].str.split(' to ', n=1, expand=True)
    cw.loc[:,lc_col] = t[0]
    cw.loc[:,'Value'] = cw.Value.astype(str)
    static = [x for x in list(cw['Description']) if ' to ' not in x]
    cw = cw[['Value',lc_col]]

    # remove no change records
    df = df[~df['Class_name'].isin(static)]

    # assign LC for time period
    df = df.merge(cw, left_on='Class_name', right_on='Value', how='left')

    # assign SID for time period
    df.loc[:, sid] = [x for x in range(1, len(df)+1)]

    # return results
    return df[[sid, lc_col, 'geometry']]


def change_segs_v1():
    """
    change_segs_v1: version 1 of change segments and psegs. psegs are the same as 2022 ed. (T3 unioned with parcels)
                    and change segments are areas of change from T1 to T2 unioned with change from T2 to T3 unioned with
                    psegs.
    """ 
    # 1. Assign unique SID to T3 segmentation
    # print("T3")
    # t3 = gpd.read_file(gdbPath, layer=layers['t3'], mask=bbox)
    # t3 = t3[['Class_name','geometry']]
    # t3.rename(columns={'Class_name' :'T3_LC'}, inplace=True)
    # t3.loc[:,'T3_SID'] = [int(x) for x in range(1, len(t3)+1)]
    # t3.crs = "EPSG:5070"
    # t3.to_file(f"{test_input}/segments.gpkg",layer='t3',driver="GPKG")
    # t3 = gpd.read_file(f"{test_input}/segments.gpkg",layer='t3')

    # 2. Isolate change between t2 and t3, assign LC and ID to T2
    print("T2")
    # t2 = gpd.read_file(gdbPath, layer=layers['t2_t3'], mask=bbox)
    # t2 = assign_change(t2, "T2")
    # t2.crs = "EPSG:5070"
    # t2.to_file(f"{test_input}/segments.gpkg",layer='t2',driver="GPKG")
    t2 = gpd.read_file(f"{test_input}/segments.gpkg",layer='t2')

    # 3. Isolate change between t1 and t2, assign LC and ID to T1
    print("T1")
    # t1 = gpd.read_file(gdbPath, layer=layers['t1_t2'], mask=bbox)
    # t1 = assign_change(t1, "T1")
    # t1.crs = "EPSG:5070"
    # t1.to_file(f"{test_input}/segments.gpkg",layer='t1',driver="GPKG")
    t1 = gpd.read_file(f"{test_input}/segments.gpkg",layer='t1')

    # # 4. read in parcels, convert to single part, and assign PID
    # print("parcels")
    # parcels = gpd.read_file(parcels_path, mask=bbox) # in dp workflow - this should be the 1-meter parcels
    # parcels = parcels.explode().reset_index()
    # parcels = parcels[['geometry']]
    # parcels.loc[:, 'PID'] = [int(x) for x in range(1, len(parcels)+1)]

    # 5. create t3 psegs used in static models - union t3 segments with parcels
    print("psegs")
    # t3_psegs = gpd.overlay(t3, parcels, how='union')
    # del t3 
    # del parcels 
    # t3_psegs = t3_psegs[~t3_psegs['T3_SID'].isna()] # remove records of parcels with no LC
    # t3_psegs.loc[:, 'PSID'] = [int(x) for x in range(1, len(t3_psegs)+1)]
    # t3_psegs.crs = "EPSG:5070"
    # t3_psegs.to_file(f"{output_fold}/psegs.gpkg", layer='psegs_v1', driver="GPKG")
    t3_psegs = gpd.read_file(f"{output_fold}/psegs.gpkg", layer='psegs_v1')

    # 6. union change segments
    print("change")
    chg = gpd.overlay(t1, t2, how='union')
    del t1
    del t2
    chg = gpd.overlay(chg, t3_psegs, how='union')
    del t3_psegs
    # only keep records of change (either T1 or T2 data exists)
    chg = chg[(~chg['T1_SID'].isna()) | (~chg['T2_SID'].isna())] 

    # assign T2 where it is missing - only missing in cases of change from T1 to T2 and T2 == T3
    chg.loc[chg['T2_LC'].isna(), 'T2_LC'] = chg.T3_LC
    print(chg)

    # write results
    chg.crs = "EPSG:5070"
    chg.to_file(f"{output_fold}/change_segs.gpkg", layer='change_v1', driver="GPKG")

def change_segs_v2():
    """
    change_segs_v2: proposed workflow for creation of change segments and psegs. 
                    psegs are 1:1 related to change by PSCID, t3 unioned with parcels unioned with change footprint
                    change segments are areas of change from T1 to T2 unioned with change from T2 to T3 unioned with psegs.
    """ 
    # 1. Assign unique SID to T3 segmentation
    print("T3")
    t3 = gpd.read_file(gdbPath, layer=layers['t3'], mask=bbox)
    t3 = t3[['Class_name','geometry']]
    t3.rename(columns={'Class_name' :'T3_LC'}, inplace=True)
    t3.loc[:,'T3_SID'] = [int(x) for x in range(1, len(t3)+1)]
    t3.crs = "EPSG:5070"
    t3.to_file(f"{test_input}/segments.gpkg",layer='t3',driver="GPKG")
    # t3 = gpd.read_file(f"{test_input}/segments.gpkg",layer='t3')

    # 2. Isolate change between t2 and t3, assign LC and ID to T2
    print("T2")
    t2 = gpd.read_file(gdbPath, layer=layers['t2_t3'], mask=bbox)
    t2 = assign_change(t2, "T2")
    t2.crs = "EPSG:5070"
    t2.to_file(f"{test_input}/segments.gpkg",layer='t2',driver="GPKG")
    # t2 = gpd.read_file(f"{test_input}/segments.gpkg",layer='t2')

    # 3. Isolate change between t1 and t2, assign LC and ID to T1
    print("T1")
    t1 = gpd.read_file(gdbPath, layer=layers['t1_t2'], mask=bbox)
    t1 = assign_change(t1, "T1")
    t1.crs = "EPSG:5070"
    t1.to_file(f"{test_input}/segments.gpkg",layer='t1',driver="GPKG")
    # t1 = gpd.read_file(f"{test_input}/segments.gpkg",layer='t1')

    # 4. read in parcels, convert to single part, and assign PID
    print("parcels")
    parcels = gpd.read_file(parcels_path, mask=bbox) # in dp workflow - this should be the 1-meter parcels
    parcels = parcels.explode().reset_index()
    parcels = parcels[['geometry']]
    parcels.loc[:, 'PID'] = [int(x) for x in range(1, len(parcels)+1)]

    # 5. create t3 psegs used in static models - union t3 segments with parcels
    print("psegs")
    t3_psegs = gpd.overlay(t3, parcels, how='union')
    del t3 
    del parcels 
    t3_psegs = t3_psegs[~t3_psegs['T3_SID'].isna()] # remove records of parcels with no LC
    t3_psegs.loc[:, 'PSID'] = [int(x) for x in range(1, len(t3_psegs)+1)]

    # 6. union change segments
    print("change")
    chg = gpd.overlay(t1, t2, how='union')
    del t1
    del t2
    chg = gpd.overlay(chg, t3_psegs, how='union')
    del t3_psegs

    # assign unique ID for Parcel, Segments, Change, PSCID
    chg.loc[:, 'PSCID'] = [int(x) for x in range(1, len(chg)+1)]
    chg.crs = "EPSG:5070"
    chg[['PID', 'T3_SID', 'PSID', 'PSCID', 'T3_LC', 'geometry']].to_file(f"{output_fold}/psegs.gpkg", layer='psegs_v2_1', driver="GPKG")

    # only keep records of change (either T1 or T2 data exists)
    chg = chg[(~chg['T1_SID'].isna()) | (~chg['T2_SID'].isna())] 

    # assign T2 where it is missing
    chg.loc[chg['T2_LC'].isna(), 'T2_LC'] = chg['T3_LC'] # change from T1 to T2 and T2 == T3
    chg.loc[chg['T1_LC'].isna(), 'T1_LC'] = chg['T2_LC'] # change from T2 to T3 and T1 == T2

    # write results
    chg.to_file(f"{output_fold}/change_segs.gpkg", layer='change_v2', driver="GPKG")

if __name__=="__main__":
    # paths
    proj_path = r'C:/Users/smcdonald/Documents/Data/LULC_2024Design/Design/DataPrep/segmentation'
    output_fold = f"{proj_path}/test_output"
    test_input = f"{proj_path}/test_inputs"
    gdbPath = f"{proj_path}/segments.gdb"
    layers = {
        'bbox'  : 'bbox_test',
        't3'    : 'lc_segs',
        't2_t3' : 'lc_segs_t2_t3',
        't1_t2' : 'lc_segs_t1_t2',
    }
    parcels_path = f"{proj_path}/parcels.shp"

    # testing within bbox
    bbox = gpd.read_file(gdbPath, layer=layers['bbox'])

    # # test version 1 -- first attempt. Don't use.
    # change_segs_v1()

    # test version 2 -- propsed workflow
    change_segs_v2()