#include <iostream>
#include <boost/program_options.hpp>
#include "geotiff.h"
#include "gdal_priv.h"
#include "ogr_api.h"

using namespace std;
namespace po = boost::program_options;



void transform()
{
     OGRSpatialReference    oUTM, *poLatLong;

     OGRCoordinateTransformation *poTransform;

     oUTM.SetProjCS("UTM 17 / WGS84");
    oUTM.SetWellKnownGeogCS( "WGS84" );
    oUTM.SetUTM( 17 );

    poLatLong = oUTM.CloneGeogCS();
    
    poTransform = OGRCreateCoordinateTransformation( &oUTM, poLatLong );
    if( poTransform == NULL )
    {
        ...
    }
    
    ...

    if( !poTransform->Transform( nPoints, x, y, z ) )
    ...
}


int main(int argc, char* argv[])
{
    po::options_description desc("Allowed options");
    size_t side_length;
    size_t iterations;
    size_t count;
    size_t depth;
    size_t block;
    desc.add_options()
        ("help","This reads a raster image and remaps it.")
        ("size,s", po::value<size_t>(&side_length)->default_value(100),
         "length of a side of the raster")
        ("depth,d", po::value<size_t>(&depth)->default_value(100),
         "number of land use types")
        ("block,b", po::value<size_t>(&block)->default_value(32),
         "size of blocks")
        ("iter,i",po::value<size_t>(&iterations)->default_value(1),
         "number of times to run test during a single timing run")
        ("count,c",po::value<size_t>(&count)->default_value(1),
         "number of times to run sets of iterations of all tests")
        ("tiff", po::value<std::string>(),"filename of a TIFF to read")
        ;

    po::variables_map vm;
    auto parsed_options=po::parse_command_line(argc,argv,desc);
    po::store(parsed_options, vm);
    po::notify(vm);

    if (vm.count("help")) {
        cout << desc << endl;
        return 1;
    }

    const char* filename = "blah";

    GDALAllRegister();
    GDALDataset *poDataset = static_cast<GDALDataset*>(
                                            GDALOpen(filename,GA_ReadOnly));
    if ( poDataset == NULL ) {
       cout << "Cannot open dataset" << endl;
       return(1);
    }

    cout << "Driver: " <<
            poDataset->GetDriver()->GetDescription() << "/"<<
            poDataset->GetDriver()->GetMetadataItem( GDAL_DMD_LONGNAME )
            << endl;

    cout << "Size is " <<
            poDataset->GetRasterXSize(), poDataset->GetRasterYSize() <<" "<<
            poDataset->GetRasterCount() << endl;

    if( poDataset->GetProjectionRef()  != NULL )
        cout << "Projection is" << poDataset->GetProjectionRef() << endl;


    double adfGeoTransform[6];
    if( poDataset->GetGeoTransform( adfGeoTransform ) == CE_None )
    {
        cout << "Origin = "<<
                adfGeoTransform[0]<<" "<< adfGeoTransform[3] << endl;

        cout << "Pixel Size = " <<
                adfGeoTransform[1] <<" "<< adfGeoTransform[5] << endl;;
    }

    GDALClose(poDataset);
    return 0;
}
