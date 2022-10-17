import MVT from 'ol/format/MVT';
import Map from 'ol/map';
import VectorTileLayer from 'ol/layer/VectorTile';
import VectorTileSource from 'ol/source/VectorTile';
import View from 'ol/View';
import TileJSON from 'ol/source/TileJSON';
import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import XYZ from 'ol/source/XYZ';
import { createXYZ } from 'ol/tilegrid';
import Projection from 'ol/proj/Projection';
import { register } from 'ol/proj/proj4';
import proj4 from 'proj4';
import { Fill, Stroke, Style } from 'ol/style';
import LayerSwitcher from 'ol-layerswitcher';

import 'ol/ol.css';
import 'ol-layerswitcher/src/ol-layerswitcher.css';

const defaultStyle = new Style({
  fill: new Fill({
    color: '#FDDFDF'//'#ADD8E6'
  }),
  stroke: new Stroke({
    color: '#880000',
    width: 1
  })
});

const defaultGeoserverStyle = new Style({
  fill: new Fill({
    color: '#DEFDE0'//'#ADD8E6'
  }),
  stroke: new Stroke({
    color: '#880000',
    width: 1
  })
});

// note the {-y} 
const topoGeoserverVectorTileUrl = 'http://192.168.56.101:8080/geoserver/gwc/service/tms/1.0.0/gijs%3Atopography_object@EPSG%3A28992@pbf/{z}/{x}/{-y}.pbf';
const topoVectorTileUrl = 'http://192.168.56.101:8081/{z}/{x}/{-y}.pbf';

const centerX = 92551.000;
const centerY = 436790.000;
const centerPoint = [centerX, centerY];

// definition of Dutch coordinate system from
// https://pdok-ngr.readthedocs.io/handleidingen.html#in-de-browser-proj4js
// N.B. this differs from the definition at https://epsg.io/28992 !
proj4.defs('EPSG:28992', "+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889"
           + " +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel +units=m"
           + " +towgs84=565.2369,50.0087,465.658,-0.406857330322398,0.350732676542563,-1.8703473836068,4.0812"
           + " +no_defs");
register(proj4);

// extents for Netherlands from
// https://www.geonovum.nl/uploads/standards/downloads/nederlandse_richtlijn_tiling_-_versie_1.1.pdf
const extent = [-285401.92, 22598.08, 595401.92, 903401.92];

// create EPSG:28992 projection
const proj28992 = new Projection({
  code: 'EPSG:28992',
  extent: extent,
  unit: 'm'
});

// layer for ArcGIS world map
const arcGisLayer = new TileLayer({
  opacity: 1,
  source: new XYZ({
    attributions: 'Tiles © <a href="https://services.arcgisonline.com/ArcGIS/'
     + 'rest/services/World_Imagery/MapServer">ArcGIS</a> 2019',
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/'
     + 'World_Imagery/MapServer/tile/{z}/{y}/{x}'
  }),
  title: 'ArcGIS world imagery'//,
//  type: 'base'
});

// wms layer using geoserver
const wmsLayer = new TileLayer({
  source: new TileWMS({
    url: 'http://192.168.56.101:8080/geoserver/gijs/wms',
	params: { 'LAYERS': 'gijs:topography_object', 'TILED': true },
	serverType: 'geoserver',
	projection: proj28992
  }),
  title: 'WMS',
  visible: false
});

// vector tile layer using python + postgis
const bgtLayer = new VectorTileLayer({
  declutter: false,
  style: defaultStyle,
  source: new VectorTileSource({
    format: new MVT(),
	projection: proj28992,
    url: topoVectorTileUrl
  }),
  title: 'Vector Tile Python',
  visible: false
});

// vector tile layer using geoserver
const bgtGeoserverLayer = new VectorTileLayer({
  declutter: false,
  style: defaultGeoserverStyle,
  source: new VectorTileSource({
    format: new MVT(),
	projection: proj28992,
    url: topoGeoserverVectorTileUrl
  }),
  title: 'Vector Tile Geoserver',
  visible: false
});

// create map
const map = new Map({
  target: 'map-container',
  view: new View({
    minZoom: 3,
    maxZoom: 22,
    projection: proj28992,
    center: centerPoint,
    zoom: 13
  })
});

// add layers
map.addLayer(arcGisLayer);
map.addLayer(bgtGeoserverLayer);
map.addLayer(bgtLayer);
map.addLayer(wmsLayer);

let layerSwitcher = new LayerSwitcher();
map.addControl(layerSwitcher);