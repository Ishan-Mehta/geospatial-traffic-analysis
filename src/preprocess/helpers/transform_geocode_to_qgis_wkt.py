import pandas as pd
from io import StringIO

# 1. Load your data
# (I am using a string here for the demo, but you will use: df = pd.read_csv('your_file.csv'))
# csv_data = """Zone,Sl_No,Road_Name,Computed_Start_Point,Computed_End_Point,Full_Coordinate_Chain,Coordinate_Count,Status,Original_Via
# Mahadevapura -2,S-02,Anandapur Road,Anandapura,Maragondanahalli,"13.0249798,77.6944104|13.0249798,77.6944104|13.0373995,77.69272099999999",3,OK,Anandapura
# Mahadevapura -2,S-05,Hanagalipura Road,Hanagalipura,Hanagalipura,"12.9628669,77.57750899999999",1,INCOMPLETE_CHAIN,Hanagalipura
# Mahadevapura -3,S-08,Horamavu - Agara Road,Nanjappa Garden,Agara Junction,"13.021712,77.6557601|12.9750721,77.665865|13.0326328,77.6583345|12.9230648,77.6464534|12.923937,77.651629",5,OK,Nanjappa Garden - Babasaheb palya- Horamavu-Agara
# """

# Read the CSV
df = pd.read_csv('bangalore_roads_geocoded_chain.csv') # Replace with pd.read_csv('your_filename.csv')

# 2. Define a function to convert the string to WKT
def convert_to_wkt(coord_chain):
    try:
        # Split the chain by the pipe symbol '|'
        points = coord_chain.split('|')
        
        # If less than 2 points, it's not a line (it's a Point), handled later
        if len(points) < 2:
            return None 

        formatted_points = []
        for point in points:
            # Split "Lat,Lon" into [Lat, Lon]
            lat, lon = point.split(',')
            
            # CRITICAL STEP: Swap to "Lon Lat" for GIS standards
            # and join with a space
            formatted_points.append(f"{lon.strip()} {lat.strip()}")
        
        # Join all points with commas and wrap in LINESTRING()
        return f"LINESTRING ({', '.join(formatted_points)})"
    except Exception as e:
        return None

# 3. Apply the function
df['wkt_geometry'] = df['Full_Coordinate_Chain'].apply(convert_to_wkt)

# 4. Filter: Keep only valid Linestrings (Removes "INCOMPLETE_CHAIN" or single points)
df_clean = df.dropna(subset=['wkt_geometry'])

# 5. Save to a new CSV
df_clean.to_csv('bangalore_roads_wkt.csv', index=False)

print(f"Processed {len(df)} rows. Saved {len(df_clean)} valid routes to 'bangalore_roads_wkt.csv'.")
print(df_clean[['Road_Name', 'wkt_geometry']].head())