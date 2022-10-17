import http.server
import socketserver
import re
import psycopg2
import json

# Database to connect to
DATABASE = {
    'user':     'topodata',
    'password': '*****',
    'host':     'localhost',
    'port':     '5432',
    'database': 'topodata'
    }

# Table to query for MVT data, and columns to
# include in the tiles.
TABLE = {
    'table':       'data.topography_object',
    'srid':        '28992',
    'geomColumn':  'geometry',
    'attrColumns': 'id, level'
    }  

# HTTP server information
HOST = '0.0.0.0'
PORT = 8081


########################################################################

class TileRequestHandler(http.server.BaseHTTPRequestHandler):

    DATABASE_CONNECTION = None

    # Search REQUEST_PATH for /{z}/{x}/{y}.{format} patterns
    def pathToTile(self, path):
        m = re.search(r'^\/(\d+)\/(\d+)\/(\d+)\.(\w+)', path)
        if (m):
            return {'zoom':   int(m.group(1)), 
                    'x':      int(m.group(2)), 
                    'y':      int(m.group(3)), 
                    'format': m.group(4)}
        else:
            return None


    # Do we have all keys we need? 
    # Do the tile x/y coordinates make sense at this zoom level?
    def tileIsValid(self, tile):
        if not ('x' in tile and 'y' in tile and 'zoom' in tile):
            return False
        if 'format' not in tile or tile['format'] not in ['pbf', 'mvt']:
            return False
        size = 2 ** tile['zoom'];
        if tile['x'] >= size or tile['y'] >= size:
            return False
        if tile['x'] < 0 or tile['y'] < 0:
            return False
        return True


    # Calculate envelope in "Amersfoort/RD new" (https://epsg.io/28992)
    def tileToEnvelope(self, tile):
        # Width and height of world in EPSG:28992
        worldRdMinX = -285401.92
        worldRdMaxX = 595401.92
        worldRdMinY = 22598.08
        worldRdMaxY = 903401.92
        worldRdSize = worldRdMaxX - worldRdMinX
        # Width and height in tiles
        worldTileSize = 2 ** tile['zoom']
        # Tile width in EPSG:28992
        tileRdSize = worldRdSize / worldTileSize
        
        # Calculate geographic bounds from tile coordinates
        # XYZ tile coordinates are in "image space" so origin is
        # top-left, not bottom right
        env = dict()
        env['xmin'] = worldRdMinX + tileRdSize * tile['x']
        env['xmax'] = worldRdMinX + tileRdSize * (tile['x'] + 1)
        env['ymin'] = worldRdMinY + tileRdSize * (tile['y'] + 1)
        env['ymax'] = worldRdMinY + tileRdSize * (tile['y'])
        return env


    # Generate SQL to materialize a query envelope in EPSG:28992.
    # Densify the edges a little so the envelope can be
    # safely converted to other coordinate systems.
    def envelopeToBoundsSQL(self, env):
        DENSIFY_FACTOR = 4
        env['segSize'] = (env['xmax'] - env['xmin'])/DENSIFY_FACTOR
        sql_tmpl = 'ST_Segmentize(ST_MakeEnvelope({xmin}, {ymin}, {xmax}, {ymax}, 28992),{segSize})'
        return sql_tmpl.format(**env)


    # Generate a SQL query to pull a tile worth of MVT data
    # from the table of interest.        
    def envelopeToSQL(self, env):
        tbl = TABLE.copy()
        tbl['env'] = self.envelopeToBoundsSQL(env)
        # Materialize the bounds
        # Select the relevant geometry and clip to MVT bounds
        # Convert to MVT format
        sql_tmpl = """
            WITH 
            bounds AS (
                SELECT {env} AS geom, 
                       {env}::box2d AS b2d
            ),
            mvtgeom AS (
                SELECT ST_AsMVTGeom(ST_Transform(ST_CurveToLine(t.{geomColumn}), 28992), bounds.b2d) AS geom, 
                       {attrColumns}
                FROM {table} t, bounds
                WHERE ST_Intersects(t.{geomColumn}, ST_Transform(bounds.geom, {srid}))
            ) 
            SELECT ST_AsMVT(mvtgeom.*) FROM mvtgeom
        """
        return sql_tmpl.format(**tbl)


    # Run tile query SQL and return error on failure conditions
    def sqlToPbf(self, sql):
        # Make and hold connection to database
        if not self.DATABASE_CONNECTION:
            try:
                self.DATABASE_CONNECTION = psycopg2.connect(**DATABASE)
            except (Exception, psycopg2.Error) as error:
                self.send_error(500, "cannot connect: %s" % (str(DATABASE)))
                return None

        # Query for MVT
        with self.DATABASE_CONNECTION.cursor() as cur:
            cur.execute(sql)
            if not cur:
                self.send_error(404, "sql query failed: %s" % (sql))
                return None
            return cur.fetchone()[0]
        
        return None


    # Handle HTTP GET requests
    def do_GET(self):

        tile = self.pathToTile(self.path)
        if not (tile and self.tileIsValid(tile)):
            self.send_error(400, "invalid tile path: %s" % (self.path))
            return

        env = self.tileToEnvelope(tile)
        sql = self.envelopeToSQL(env)
        pbf = self.sqlToPbf(sql)

        self.log_message("path: %s\ntile: %s\n env: %s" % (self.path, tile, env))
        self.log_message("sql: %s" % (sql))
        
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-type", "application/vnd.mapbox-vector-tile")
        self.end_headers()
        self.wfile.write(pbf)



########################################################################


with http.server.HTTPServer((HOST, PORT), TileRequestHandler) as server:
    try:
        print("serving at port", PORT)
        server.serve_forever()
    except KeyboardInterrupt:
        if self.DATABASE_CONNECTION:
            self.DATABASE_CONNECTION.close()
        print('^C received, shutting down server')
        server.socket.close()


