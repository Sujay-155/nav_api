from flask import Flask, jsonify
from flask_cors import CORS
import json
import os
import math
import logging

app = Flask(__name__)
CORS(app)

# Configure logging for Azure
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The path to the geojson file
GEOJSON_FILE = os.path.join(os.path.dirname(__file__), 'christ_university (1).geojson')

def load_geojson_data():
    """Load and return GeoJSON data"""
    try:
        with open(GEOJSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("GeoJSON file not found")
        return None
    except json.JSONDecodeError:
        logger.error("Invalid GeoJSON format")
        return None

def find_location_by_id(data, location_id):
    """Find a location by its ID in the GeoJSON data"""
    if not data or 'features' not in data:
        return None
    
    for feature in data['features']:
        if feature.get('id') == location_id:
            return feature
    return None

def generate_simple_route(source_coords, dest_coords):
    """Generate a simple straight-line route between two points"""
    waypoints = [
        source_coords,
        [
            (source_coords[0] + dest_coords) / 2,
            (source_coords[1] + dest_coords[1]) / 2
        ],
        dest_coords
    ]
    return waypoints

@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "AR Navigation API is running", 
        "version": "1.0",
        "environment": "Azure Production",
        "app_name": "AR Campus Christ Navigation"
    })

@app.route("/christ_university.geojson")
def get_geojson():
    """Serve the complete GeoJSON file for location loading"""
    data = load_geojson_data()
    if data is None:
        return jsonify({"error": "GeoJSON file not found or invalid"}), 500
    
    logger.info("GeoJSON data served successfully")
    return jsonify(data)

@app.route("/route/<path_name>")
def get_route(path_name):
    """Get route between two locations"""
    try:
        logger.info(f"Route requested: {path_name}")
        
        data = load_geojson_data()
        if data is None:
            return jsonify({"error": "GeoJSON file not found or invalid"}), 500

        if '-to-' not in path_name:
            return jsonify({"error": "Invalid route format. Use: source_id-to-destination_id"}), 400
        
        parts = path_name.split('-to-')
        if len(parts) != 2:
            return jsonify({"error": "Invalid route format. Use: source_id-to-destination_id"}), 400
        
        source_id, dest_id = parts[0].strip(), parts[1].strip()
        
        if not source_id or not dest_id:
            return jsonify({"error": "Source and destination IDs cannot be empty"}), 400

        if source_id == dest_id:
            return jsonify({"error": "Source and destination cannot be the same"}), 400

        # Find locations
        source_location = find_location_by_id(data, source_id)
        dest_location = find_location_by_id(data, dest_id)

        if not source_location:
            return jsonify({"error": f"Source location '{source_id}' not found"}), 404
        
        if not dest_location:
            return jsonify({"error": f"Destination location '{dest_id}' not found"}), 404

        # Extract coordinates
        source_coords = source_location['geometry']['coordinates']
        dest_coords = dest_location['geometry']['coordinates']

        # Generate route
        route_coordinates = generate_simple_route(source_coords, dest_coords)
        
        # Calculate distance
        def calculate_distance(coord1, coord2):
            lat1, lon1 = math.radians(coord1[1]), math.radians(coord1[0])
            lat2, lon2 = math.radians(coord2[1]), math.radians(coord2)
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            r = 6371000
            
            return r * c

        distance = calculate_distance(source_coords, dest_coords)
        
        result = {
            "type": "generated_route",
            "coordinates": route_coordinates,
            "properties": {
                "distance": f"{int(distance)}m",
                "duration": f"{int(distance/80)}min",
                "source_id": source_id,
                "destination_id": dest_id,
                "source_name": source_location.get('properties', {}).get('name', source_id),
                "destination_name": dest_location.get('properties', {}).get('name', dest_id)
            }
        }
        
        logger.info(f"Route generated successfully: {source_id} to {dest_id}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error generating route: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

