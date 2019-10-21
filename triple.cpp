/*! This intersects the geometries of one vector and two raster
 *  datasets in order to pull out properties of the vector features,
 *  organized according to the rasters that overlap.
 *  Given: Observations of disease specified by county and date.
 *  Use NDVI Greening as a covariate. It is a 1280x1024 raster.
 *  Several tiles of NDVI greening cover a county, so we want to
 *  weight them by how much wheat is in each tile, which means
 *  counting areas of wheat in the CDLS within each tile that
 *  overlaps each county.
 *
 *  Logically, the first step is to intersect geometries. Then
 *  pull out fields of each feature as required. That's not how
 *  this code is written. The moment we read a code from the CDLS
 *  could be separate from handling its geometry. It seems that
 *  separating data access from geometry handling would make it 
 *  inefficient, but I don't know until I try.
 *
 *  The GDAL spatial reference system (SRS) is good for transforming
 *  points, but it does not describe the grid in a raster dataset.
 *  That's separate and is contained in what they call the transform.
 */
#include <iostream>
#include <exception>
#include <sstream>
#include <boost/shared_ptr.hpp>
#include <boost/program_options.hpp>
#include <boost/filesystem.hpp>
#include <boost/array.hpp>
#include <boost/make_shared.hpp>
#include <boost/iterator/iterator_facade.hpp>
#include "gdal/gdal_priv.h"
#include "gdal/ogr_api.h"
#include "gdal/ogrsf_frmts.h"


using namespace std;
namespace po = boost::program_options;

typedef boost::array<size_t,2> pl_t; // pixel/line coordinates
typedef boost::array<double,2> xy_t; // projected coordinates



std::ostream& operator<<(std::ostream& os, const boost::array<double,4>& a)
{
    return os << a[0] << " " << a[1] << " " << a[2] << " " << a[3];
}

std::ostream& operator<<(std::ostream& os, const boost::array<size_t,4>& a)
{
    return os << a[0] << " " << a[1] << " " << a[2] << " " << a[3];
}

std::ostream& operator<<(std::ostream& os, const OGREnvelope& a)
{
    return os << a.MinX << " " << a.MaxX << " " << a.MinY << " " << a.MaxY;
}

std::ostream& operator<<(std::ostream& os, const pl_t& a)
{
    return os << "p " << a[0] << " l " << a[1];
}

std::ostream& operator<<(std::ostream& os, const xy_t& a)
{
    return os << "x " << a[0] << " y " << a[1];
}



bool check_between(size_t& a, const size_t& b, const size_t& c)
{
    if (a<b) {
        std::cout << "problem with " << a << " and " << b << std::endl;
        a=b;
        return true;
    }
    if (a>c) {
        std::cout << "problem with " << a << " and " << b << std::endl;
        a=c;
        return true;
    }
    return false;
}


bool region_check(boost::array<size_t,4>& lims,
                  const boost::array<size_t,4>& region)
{
    bool fixed=false;
    lims[0]=max(lims[0],region[0]);
    lims[0]=min(lims[0],region[1]);
    lims[1]=max(lims[1],region[0]);
    lims[1]=min(lims[1],region[1]);
    fixed = fixed || check_between(lims[0],region[0],region[1]);
    fixed = fixed || check_between(lims[1],region[0],region[1]);
    fixed = fixed || check_between(lims[2],region[2],region[3]);
    // The compiler did not modify lims[3] when it was out of bounds. Weird.
    // Don't trust this code.
    fixed = fixed || check_between(lims[3],region[2],region[3]);
    return fixed;
}



/*! Reads a subarray of a band.
 *  The returned shared_ptr is of X width bounds[1]-bounds[0]
 *  and Y width bounds[3]-bounds[2]. You get a value with
 *  iX + iY*(bounds[1]-bounds[0])
 */
boost::shared_ptr<std::vector<unsigned char> >
read_sub_array( GDALRasterBand *poBand, const boost::array<size_t,4>& bounds)
{
    CPLAssert( poBand->GetRasterDataType() == GDT_Byte );

    size_t nXSize=bounds[1]-bounds[0];
    size_t nYSize=bounds[3]-bounds[2];
    auto buffer = boost::make_shared<std::vector<unsigned char> >(nXSize*nYSize);
    CPLErr io_err = poBand->RasterIO(GF_Read,
                                     bounds[0],bounds[2],
                                     nXSize, nYSize,
                                     &(*buffer)[0],
                                     nXSize, nYSize,
                                     GDT_Byte,
                                     0, 0);
    if (io_err != CPLE_None) {
        std::stringstream ss;
        ss << "Error " << CPLError << " reading raster band.";
        throw std::runtime_error(ss.str());
    }

    //cout << "Retrieving data x " << nXSize << " Y " << nYSize
    //     << " total size " << nXSize*nYSize << std::endl;
    return buffer;
}



/*! Iterator to features in a layer of the data source.
 *  The feature is allocated each time this is incremented and
 *  must be deallocated with OGRFeature::DestroyFeature().
 */
class feature_iterator
    : public boost::iterator_facade<feature_iterator,
                                    boost::shared_ptr<OGRFeature>,
                                    boost::forward_traversal_tag
                                    >
{
    OGRLayer* m_layer;
    boost::shared_ptr<OGRFeature> m_feature;
public:
    //feature_iterator() : m_layer(nullptr), m_feature(nullptr) {}
    explicit feature_iterator(OGRLayer* layer,
                              boost::shared_ptr<OGRFeature> feature)
        : m_layer(layer), m_feature(feature) {}
private:
    friend class boost::iterator_core_access;
    void increment() {
        m_feature=boost::shared_ptr<OGRFeature>(m_layer->GetNextFeature(),
                                             OGRFeature::DestroyFeature);
    }
    bool equal(feature_iterator const& other) const
    {
        return this->m_feature == other.m_feature;
    }
    reference dereference() { return m_feature; }
};



class SafeOGRDataSource
{
    OGRDataSource* m_source;
public:
    SafeOGRDataSource(std::string filename) {
        m_source = OGRSFDriverRegistrar::Open(filename.c_str(),FALSE);
        if (NULL == m_source) {
            throw std::runtime_error("Could not open OGR file.");
        }
    }
    ~SafeOGRDataSource() {
        OGRDataSource::DestroyDataSource(m_source);
    }

    OGRLayer* GetLayerByName(const std::string& name) {
        return m_source->GetLayerByName(name.c_str());
    }

    boost::array<feature_iterator,2>
    forward(std::string layer_name)
    {
        OGRLayer *layer = m_source->GetLayerByName(layer_name.c_str());
        if (NULL == layer) {
            throw std::runtime_error("Could not get layer.");
        }
        
        layer->ResetReading();
        auto feature = boost::shared_ptr<OGRFeature>(layer->GetNextFeature(),
                                                  OGRFeature::DestroyFeature);
        OGRFeature* end = 0;
        boost::array<feature_iterator,2> interval =
            { feature_iterator(layer,feature),
              feature_iterator(layer,boost::shared_ptr<OGRFeature>(end))
            };
        return interval;
    }
};



/*! Given a bounding box in projected coordinates, find the raster coordinates.
 *  I have an OGR (vector) feature and want to find the raster pixels
 *  that overlap with that feature, so I take the bounding box of the feature
 *  and loop over the pixels in the raster that might overlap.
 *
 *  OGREnvelope is just the four sides of a box in the projected coordinates.
 *  geoTransform comes from GDALDataset::GetGeoTransform().
 *     See the GDALDataset class API docs for details on what the values are.
 *  Returns: MinX, MaxX, MinY, MaxY.
 */
boost::array<size_t,4> raster_bounds(OGREnvelope* vector_bounds,
                                     double* geoTransform)
{
    OGREnvelope* vb=vector_bounds;
    std::vector<xy_t> corners(4);
    corners[0][0]=vb->MinX; // longhand for Intel compiler
    corners[0][1]=vb->MinY;
    corners[1][0]=vb->MinX;
    corners[1][1]=vb->MaxY;
    corners[2][0]=vb->MaxX;
    corners[2][1]=vb->MinY;
    corners[3][0]=vb->MaxX;
    corners[3][1]=vb->MaxY;

    // The supplied geoTransform is a 2x2 linear transformation
    // from pixel space to projection space, so we invert it.
    double* gt=geoTransform;
    double inv_det = 1.0/(gt[1]*gt[5]-gt[2]*gt[4]);
    
    for (int pidx=0; pidx<corners.size(); pidx++) {
        double x = corners[pidx][0]-gt[0];
        double y = corners[pidx][1]-gt[3];
        corners[pidx][0] = inv_det*( gt[5]*x - gt[2]*y);
        corners[pidx][1] = inv_det*(-gt[4]*x + gt[1]*y);
    }

    double minx=corners[0][0],maxx=corners[0][0];
    double miny=corners[0][1],maxy=corners[0][1];
    for (int midx=0; midx<corners.size(); midx++) {
        if (corners[midx][0]<minx) minx=corners[midx][0];
        if (corners[midx][0]>maxx) maxx=corners[midx][0];
        if (corners[midx][1]<miny) miny=corners[midx][1];
        if (corners[midx][1]>maxy) maxy=corners[midx][1];
    }
    boost::array<size_t,4> raster_bounds;
    raster_bounds[0]=static_cast<size_t>(std::floor(minx));
    raster_bounds[1]=static_cast<size_t>(std::ceil(maxx))+1;
    raster_bounds[2]=static_cast<size_t>(std::floor(miny));
    raster_bounds[3]=static_cast<size_t>(std::ceil(maxy))+1;
    //std::cout << "envelope " << *vb << endl;
    //std::cout << "raster_bounds " << raster_bounds << std::endl;
    return raster_bounds;
}



/*! Transform an OGREnvelope to another coordinate system. */
void bounds_transform(OGREnvelope& bounds, OGRCoordinateTransformation& trans)
{
    double cboundsx[2] = { bounds.MinX, bounds.MaxX };
    double cboundsy[2] = { bounds.MinY, bounds.MaxY };
    trans.Transform(2,cboundsx, cboundsy);
    bounds.MinX=cboundsx[0];
    bounds.MaxX=cboundsx[1];
    bounds.MinY=cboundsy[0];
    bounds.MaxY=cboundsy[1];
}



/*! Transform from scanline pixel/line to projected xy. */
xy_t pl_to_xy(const pl_t& pl, const double* geoTransform)
{
    xy_t xy;
    xy[0]=geoTransform[0]+pl[0]*geoTransform[1]+pl[1]*geoTransform[2];
    xy[1]=geoTransform[3]+pl[0]*geoTransform[4]+pl[1]*geoTransform[5];
    return xy;
}

/*! Transform from scanline pixel/line to projected xy.
 *  This version accepts half pixels.
 */
xy_t pl_to_xy(const xy_t& pl, const double* geoTransform)
{
    xy_t xy;
    xy[0]=geoTransform[0]+pl[0]*geoTransform[1]+pl[1]*geoTransform[2];
    xy[1]=geoTransform[3]+pl[0]*geoTransform[4]+pl[1]*geoTransform[5];
    return xy;
}


void tile_to_polygon(OGRPolygon* polygon,
                     const pl_t& pl,
                     double* geoTransform)
{
    std::vector<pl_t> corners(5);
    corners[0][0]=pl[0];
    corners[0][1]=pl[1];
    corners[1][0]=pl[0]+1;
    corners[1][1]=pl[1];
    corners[2][0]=pl[0]+1;
    corners[2][1]=pl[1]+1;
    corners[3][0]=pl[0];
    corners[3][1]=pl[1]+1;
    corners[4][0]=pl[0];
    corners[4][1]=pl[1];

    OGRLinearRing* ring = polygon->getExteriorRing();
    OGRRawPoint pts[corners.size()];
    for (int cidx=0; cidx<corners.size(); cidx++) {
        auto xy=pl_to_xy(corners[cidx],geoTransform);
        pts[cidx].x=xy[0];
        pts[cidx].y=xy[1];
    }
    // OGRLinearRing::setPoints does a memcpy inside.
    ring->setPoints(corners.size(), pts, 0);
}


double get_area(OGRGeometry* geom)
{
    double area=0;
    if (0==geom) return 0;

    switch (geom->getGeometryType()) {
    case wkbPolygon:
        area=static_cast<OGRPolygon*>(geom)->get_Area();
        break;
    case wkbMultiPolygon:
        area=static_cast<OGRMultiPolygon*>(geom)->get_Area();
        break;
    case wkbGeometryCollection:
        {
            OGRGeometryCollection* gc
                = static_cast<OGRGeometryCollection*>(geom);
            for (size_t gc_idx=0; gc_idx<gc->getNumGeometries(); gc_idx++) {
                area+=get_area(gc->getGeometryRef(gc_idx));
            }
        }
        break;
    default:
        area=0;
        break;
    }

    return area;
}



template<typename T>
bool in_string(T val, const T codelist[])
{
    int idx=0;
    while (codelist[idx]!=0) {
        if (codelist[idx]==val) return true;
        idx++;
    }
    return false;
}

const unsigned char like_wheat[] = {21,22,23,24,26,27,28,225,226,
                                    230,233,234,235,236,
                                    237,238,240,254,0};
bool is_wheat(unsigned char val) {
    return in_string(val,like_wheat);
}

const int fips_not_continental_us[] = {2, 60, 66, 15, 72, 78, 0};

bool continental_us(int state_fips)
{
    return !in_string(state_fips,fips_not_continental_us);
}


/* GIMMS NDVI doesn't specify its ellipsoid in the SRS
   metadata, but it does have the Clarke 1866 ellipsoid 
   in the human-readable text string. GDAL guesses the WGS84
   ellipsoid, but we'll just replace that with the NAD27,
   which wikipedia says is what the Clarke 1866 ellipsoid's
   datum is called. We'll use this instead of the file's
   metadata.

The metadata file in the GIMMS download has this:
Projection = Albers Equal Area Conic, Clarke 1866 ellipsoid
Units = Meters
Origin of latitudes = 45 deg
Central Meridian = -103 deg
First standard parallel = 20 deg
Second standard parallel = 60 deg
Pixel size = 8000 meters, 8km
UL Map x =      -5120003.4
UL Map y =       4096001.0
LR Map x =        5111996.6
LR Map y =       -4087999.0
UL Map x (degrees) =        157.41200
UL Map y (degrees) =        54.626000
LR Map x (degrees) =       -62.142828
LR Map y (degrees) =       -2.3819384
Num. of samples =         1280
Num. of lines =         1024
Data Type = 16 bit
 */
const char* GIMMS_WKT =
"PROJCS[\"Albers Equal Area Conic, Clarke 1866 ellipsoid\","
"    GEOCS[\"NAD 27\","
"        DATUM[\"NAD_1866\","
"            SPHEROID[\"NAD 27\",6378137,298.257223563]],"
"        PRIMEM[\"Greenwich\",0],"
"        UNIT[\"degree\",0.0174532925199433]],"
"    PROJECTION[\"Albers_Conic_Equal_Area\"],"
"    PARAMETER[\"standard_parallel_1\",20],"
"    PARAMETER[\"standard_parallel_2\",60],"
"    PARAMETER[\"latitude_of_center\",45],"
"    PARAMETER[\"longitude_of_center\",-103],"
"    PARAMETER[\"false_easting\",0],"
"    PARAMETER[\"false_northing\",0],"
"    UNIT[\"metre\",1,"
"        AUTHORITY[\"EPSG\",\"9001\"]]]";
const char* GIMMS_PROJ4 = "+proj=aea +lat_1=20 +lat_2=60 +lat_0=45 " 
    "+lon_0=-103 +x_0=0 +y_0=0 +ellps=NAD27 +units=m +no_defs ";



boost::filesystem::path file_argument(po::variables_map& vm,std::string name)
{
    boost::filesystem::path p;
    if (vm.count(name)<1) {
        std::cerr << "Use --" << name << " to specify a file." << std::endl;
    } else {
        boost::filesystem::path p_try = vm[name].as<vector<string>>()[0];
        if (!boost::filesystem::exists(p_try)) {
            std::cerr << "Cannot find file " << p_try <<" for "
                      << name << std::endl;
        }
        else if (boost::filesystem::is_directory(p_try)) {
            std::cerr << "You specified a directory for " << p_try
                      << " for " << name << std::endl;
        } else {
            p=p_try;
        }
    }
    return p;
}



void test_raster_bounds()
{
    OGREnvelope b;
    b.MinX=775655;
    b.MaxX=777979;
    b.MinY=946065;
    b.MaxY=949358;
    double xform[] = {-2.3561e+06, 30, 0, 3.1726e+06, 0, -30};
    boost::array<size_t,4> res = raster_bounds(&b, xform);
    cout << b << endl;
    cout << res << endl;
}



int main(int argc, char* argv[])
{
    po::options_description desc("Allowed options");
    size_t county_cnt;
    int feature_idx;
    bool test=false;
    bool by_point=false;
    desc.add_options()
        ("help","This reads a raster image and remaps it.")
        ("count,c",po::value<size_t>(&county_cnt)->default_value(0),
         "number of counties to process")
        ("feature",po::value<int>(&feature_idx)->default_value(0),
         "process only the feature with this geoid")
        ("point",po::bool_switch(&by_point),"Each tile is in or out")
        ("test",po::bool_switch(&test),"run test code")
        ("cdls", po::value<vector<string>>(),"raster of usage codes")
        ("counties", po::value<vector<string>>(),"shapefile of counties")
        ("ndvi", po::value<vector<string>>(),"raster of greening")
        ;

    po::variables_map vm;
    auto parsed_options=po::parse_command_line(argc,argv,desc);
    po::store(parsed_options, vm);
    po::notify(vm);

    if (vm.count("help")) {
        std::cout << desc << std::endl;
        return(0);
    }
    
    if (test) {
        test_raster_bounds();
        return(0);
    }

    std::string cdls = file_argument(vm,"cdls").string();
    std::string counties = file_argument(vm,"counties").string();
    std::string ndvi = file_argument(vm,"ndvi").string();
    if (cdls.empty() || counties.empty() || ndvi.empty()) {
        return(3);
    }

    // Initialize spatial libraries.

    OGRRegisterAll();
    GDALAllRegister();

    // Open files for metadata.

    GDALDataset *cdls_ds = static_cast<GDALDataset*>(
                             GDALOpen(cdls.c_str(),GA_ReadOnly));
    if ( NULL == cdls_ds ) {
       cout << "Cannot open dataset " << endl;
       return(1);
    }
    GDALRasterBand *cdls_band = cdls_ds->GetRasterBand(1);
    if (NULL == cdls_band) {
        cerr << "Cannot find raster band for CDLS dataset." << endl;
        return(1);
    }

    GDALDataset *ndvi_ds = static_cast<GDALDataset*>(
                                GDALOpen(ndvi.c_str(),GA_ReadOnly));
    if ( NULL == ndvi_ds ) {
        cout << "Cannot open dataset " << ndvi << endl;
       return(1);
    }

    SafeOGRDataSource county_source(counties);

    // We choose coordinate transformations into the GIMMS space
    // because counties are defined with lots of points and
    // CDLS squares are small, so both will convert well, whereas
    // GIMMS are 8km squares.
    auto county_layer = county_source.GetLayerByName("tl_2010_us_county10");
    OGRSpatialReference* county_srs = county_layer->GetSpatialRef();

    // NDVI - GIMMS
    OGRSpatialReference gimms_srs;
    gimms_srs.SetProjCS("Albers Equal Area, Clarke 1866 ellipsoid");
    gimms_srs.importFromProj4( GIMMS_PROJ4 );

    OGRSpatialReference cdls_srs;
    const char* cdls_proj = cdls_ds->GetProjectionRef();
    if (NULL == cdls_proj) {
        throw std::runtime_error("Cannot read projection from cdls.");
    }
    cdls_srs.importFromWkt(const_cast<char**>(&cdls_proj));

    // L - longlat, G - gimms AEA, C - CDLS AEA
    OGRCoordinateTransformation *county_gimms = 
        OGRCreateCoordinateTransformation( county_srs, &gimms_srs );

    OGRCoordinateTransformation *cdls_gimms =
        OGRCreateCoordinateTransformation( &cdls_srs, &gimms_srs );

    OGRCoordinateTransformation *gimms_cdls =
        OGRCreateCoordinateTransformation( &gimms_srs, &cdls_srs );

    double ndvi_transform[6];
    ndvi_ds->GetGeoTransform(ndvi_transform);
    GDALClose(ndvi_ds);
    ndvi_ds=0;
    
    double cdls_transform[6];
    cdls_ds->GetGeoTransform(cdls_transform);

    size_t county_idx=0;
    // Work within the bounding box of each county, one at a time.
    enum county_fields { STATE_FIPS=0, COUNTY_FIPS=1, COUNTYNS10=2,
             GEOID10=3};
    county_layer->ResetReading();
    OGRFeature* l_feature = county_layer->GetNextFeature();
    while ( l_feature != 0 ) {
        int geoid = l_feature->GetFieldAsInteger(GEOID10);
        int state_fips = l_feature->GetFieldAsInteger(STATE_FIPS);

        bool this_feature=true;
        if (feature_idx) {
            if (geoid != feature_idx) this_feature=false;
        }

        if (continental_us(state_fips) && this_feature) {
            //std::cout << "County is " << geoid << std::endl;
            OGRGeometry *l_geometry = l_feature->GetGeometryRef();
            OGRMultiPolygon* l_county_poly =
                static_cast<OGRMultiPolygon*>(l_geometry);

            l_county_poly->transform(county_gimms);
            OGRGeometry* g_county_poly = l_county_poly;

            OGREnvelope g_bounds; // MinX, MaxX, MinY, MaxY. In longlat.
            g_county_poly->getEnvelope(&g_bounds);
            
            // What subregion of NDVI covers this county?
            //std::cout << "Get bounds of ndvi for whole county." << std::endl;
            boost::array<size_t,4> ndvi_region=
                raster_bounds(&g_bounds, ndvi_transform);

            // Pull the CDLS data.
            //std::cout << "Get bounds of cdls for whole county." << std::endl;
            OGREnvelope c_cdls_bounds(g_bounds);
            bounds_transform(c_cdls_bounds, *gimms_cdls);

            boost::array<size_t,4> cdls_region=
                raster_bounds(&c_cdls_bounds, cdls_transform);

            auto cdls_arr=read_sub_array(cdls_band, cdls_region);

            // This polygon is a buffer into which to read the next tile.
            // OGR makes it impossible to just change the values of points
            // without doing a malloc somewhere. We even have to initialize
            // this with an empty ring so that the polygon is well-defined.
            OGRPolygon g_ndvi_poly;
            OGRLinearRing empty_ring;
            g_ndvi_poly.addRing(&empty_ring);

            OGRPolygon g_cdls_poly;
            g_cdls_poly.addRing(&empty_ring); // This initializes the poly.

            // For each NDVI cell, create a polygon of where it overlaps county.
            for (size_t ny=ndvi_region[2]; ny<ndvi_region[3]; ny++) {
                for (size_t nx=ndvi_region[0]; nx<ndvi_region[1]; nx++) {
                    //std::cout << "ndvicell x" << nx << " y " << ny << std::endl;
                    pl_t nxy = {{ nx, ny }};
                    tile_to_polygon(&g_ndvi_poly, nxy, ndvi_transform);

                    OGRGeometry* g_ndvi_county=
                        g_county_poly->Intersection(&g_ndvi_poly);
                    if (g_ndvi_county == 0) {
                        continue;
                    }
                    OGRGeometryCollection* g_ndvi_county_coll
                        =static_cast<OGRGeometryCollection*>(g_ndvi_county);
                    if (g_ndvi_county_coll->getNumGeometries()==0) {
                        CPLFree(g_ndvi_county);
                        continue;
                    }
                    //std::cout << "county_pixel area " <<
                    //    static_cast<OGRGeometryCollection*>(g_ndvi_county)
                    //    ->get_Area() << std::endl;

                    OGREnvelope c_ndvi_bounds;
                    // The g_ndvi_county sometimes gave 0,0,0,0 envelope.
                    // Gdal doesn't support envelope on all geometry types.
                    g_ndvi_county->getEnvelope(&c_ndvi_bounds);
                    //std::cout << "envelope of sub-county pixel in gimms "
                    //          << c_ndvi_bounds << std::endl;
                        
                    bounds_transform(c_ndvi_bounds, *gimms_cdls);
                    //std::cout << "envelope of sub-county pixel in cdls "
                    //          << c_ndvi_bounds << std::endl;

                    //std::cout << "ndvi_bounds for just one pixel" << std::endl;
                    // We check for intersection with the original
                    // bounds used to pull cdls data into memory.
                    // Those bounds came from the county geometry, so
                    // they are sure to contain the relevant tiles.
                    if (!c_cdls_bounds.Intersects(c_ndvi_bounds)) {
                        cout << "skipping extra pixel" << endl;
                        continue;
                    }
                    c_ndvi_bounds.Intersect(c_cdls_bounds);

                    boost::array<size_t,4> cdls_lims=
                        raster_bounds(&c_ndvi_bounds, cdls_transform);

                    if (region_check(cdls_lims,cdls_region)) {
                        boost::array<size_t,4> wrong_lims =
                            raster_bounds(&c_ndvi_bounds, cdls_transform);
                        std::cout << "wrong lims " << wrong_lims
                                  << " region " << cdls_region << std::endl;
                    }
                    
                    std::map<GByte,double> code_area;
                    if (cdls_lims[2]<cdls_region[2]) {
                        std::cout << "22 problem lims " << cdls_lims
                                  << " region " << cdls_region << endl;
                    }
                    if (cdls_lims[3]<cdls_region[2]) {
                        std::cout << "32 problem lims " << cdls_lims
                                  << " region " << cdls_region << endl;
                    }
                    if (cdls_lims[0]<cdls_region[0]) {
                        std::cout << "00 problem lims " << cdls_lims
                                  << " region " << cdls_region << endl;
                    }
                    if (cdls_lims[1]<cdls_region[0]) {
                        std::cout << "10 problem lims " << cdls_lims
                                  << " region " << cdls_region << endl;
                    }

                    for (size_t cy=cdls_lims[2]-cdls_region[2];
                         cy<cdls_lims[3]-cdls_region[2];
                         cy++) {
                        for (size_t cx=cdls_lims[0]-cdls_region[0];
                             cx<cdls_lims[1]-cdls_region[0];
                             cx++) {
                            double area=0;
                            if (by_point) {
                                xy_t cpl = 
                                    {{ cx+cdls_region[0]+0.5,
                                       cy+cdls_region[2]+0.5 }};
                                xy_t ccxy=pl_to_xy(cpl, cdls_transform);
                                OGRPoint pt;
                                pt.setX(ccxy[0]);
                                pt.setY(ccxy[1]);
                                pt.transform(cdls_gimms);
                                if (g_ndvi_county->Contains(&pt)) {
                                    area=900;
                                }
                            } else {
                                pl_t cxy =
                                    {{ cx+cdls_region[0],cy+cdls_region[2] }};
                                tile_to_polygon(&g_cdls_poly, cxy, cdls_transform);
                                g_cdls_poly.transform(cdls_gimms);
                            
                                OGRGeometry* g_intersect=
                                    g_ndvi_county->Intersection(&g_cdls_poly);
                                if (g_intersect) {
                                    area=get_area(g_intersect);
                                    CPLFree(g_intersect);
                                }
                            }
                            
                            if (area>0.01) { // one tile is 900
                                size_t cell=cx+cy*(cdls_region[1]-cdls_region[0]);
                                if (cell>=cdls_arr->size()) {
                                    std::cout << "Out of bounds index " << cell
                                              << " with cx " << cx << " cy " << cy
                                              << " and total size "
                                              << cdls_arr->size() << std::endl;
                                    std::cout << "ndvi_region " << ndvi_region
                                              << " " << nx << " " << ny <<std::endl;
                                    std::cout << "cdls_region "
                                              << cdls_region << std::endl;
                                    std::cout << "cdls_lims " << cdls_lims
                                              << std::endl;
                                    std::cout << "g_bounds " << g_bounds<< std::endl;
                                    std::cout << "c_cdls_bounds " << c_cdls_bounds<< std::endl;
                                    std::cout << "c_ndvi_bounds " << c_ndvi_bounds<< std::endl;
                                    
                                    std::cout << "cdls_transform ";
                                    for (size_t ti=0; ti<6; ti++) {
                                        std::cout << cdls_transform[ti] << " ";
                                    }
                                    std::cout << std::endl;
                                    pl_t llp = {{cdls_lims[0], cdls_lims[2]}};
                                    pl_t urp = {{cdls_lims[1], cdls_lims[3]}};
                                    xy_t llx = pl_to_xy(llp, cdls_transform);
                                    xy_t urx = pl_to_xy(urp, cdls_transform);
                                    std::cout << "pl ll " << llp << " ur " << urp << std::endl;
                                    std::cout << "xy ll " << llx << " ur " << urx << std::endl;
                                }
                                GByte code = cdls_arr->at(cell);

                                auto code_iter=code_area.find(code);
                                if (code_iter==code_area.end()) {
                                    code_area[code]=area;
                                } else {
                                    code_iter->second+=area;
                                }
                            }
                        }
                    }
                    
                    auto ca = code_area.begin();
                    while (ca!=code_area.end()) {
                        std::cout << geoid << "\t"
                                  << nx << "\t" << ny << "\t"
                                  << (int)(*ca).first << "\t" << (*ca).second
                                  << std::endl;
                        ca++;
                    }

                    CPLFree(g_ndvi_county);
                }
            }
            county_idx+=1;
            if (county_cnt && county_cnt==county_idx) {
                return(0);
            }
        }
        OGRFeature::DestroyFeature(l_feature);
        l_feature = county_layer->GetNextFeature();
    }

    GDALClose(cdls_ds);
    
    return 0;
}
