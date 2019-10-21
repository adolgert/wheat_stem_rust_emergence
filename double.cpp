/*! This intersects the geometries of two raster datasets in order
 *  to characterize sub-structure of the larger raster.
 *
 *  Use NDVI Greening as a covariate. It is a 1280x1024 raster.
 *  Several tiles of NDVI greening cover a county, so we want to
 *  weight them by how much wheat is in each tile, which means
 *  counting areas of wheat in the CDLS within each tile.
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

#include "raster_geometry.hpp"

using namespace std;
namespace po = boost::program_options;
using namespace imaging;

typedef boost::array<size_t,2> pl_t; // pixel/line coordinates



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
    GDALRasterBand *ndvi_band = cdls_ds->GetRasterBand(1);
    if (NULL == ndvi_band) {
        cerr << "Cannot find raster band for NDVI dataset." << endl;
        return(1);
    }

    double ndvi_transform[6];
    ndvi_ds->GetGeoTransform(ndvi_transform);
    GDALClose(ndvi_ds);
    ndvi_ds=0;

    SafeOGRDataSource county_source(counties);

    // We choose coordinate transformations into the GIMMS space
    // because counties are defined with lots of points and
    // CDLS squares are small, so both will convert well, whereas
    // GIMMS are 8km squares.
    auto county_layer = county_source.GetLayerByName("tl_2010_us_county10");

    boost::array<boost::array<size_t,2>,2> bounds;
    bounds[0][0]=0;
    bounds[0][1]=1;
    bounds[1][0]=1024;
    bounds[1][1]=1280;
    boost::array<size_t,2> blocking;
    blocking[0]=64;
    blocking[1]=64;
    boost::array<xy_blocked_iterator,2> iters=
        make_xy_blocked_iterator(bounds, blocking, false);

    auto gimms_faces = raster_faces(ndvi_band, GIMMS_PROJ4);
    auto cdls_faces = raster_faces(cdls_band);
    // cdls_faces.to_srs(gimms_srs);
    auto gimms_iter=gimms_faces.forward();
    while (gimms_iter[0]!=gimms_iter[1]) {
        // gimms_face=*cdls_iter[0];
        // gimms_bounds=bounds(gimms_face);
    //   auto cdls_in_gimms = cdls_faces.covers(bounds);
    //   auto data = load_data_bounding(cdls_ds, cdls_in_gimms);
    //   auto cdls_iter=cdls_in_gimms.forward();
    //   while (cdls_iter[0]!=cdls_iter[1]) {
    //     area=cdls_iter[0]->intersect_area(gimms_face);
    //     histogram[data[*cdls_iter[0]]]+=area;
    //     cdls_iter[0]++;
    //   }
      gimms_iter[0]++;
    }

    GDALClose(cdls_ds);
    
    return 0;
}
