#include <iostream>
#include <boost/program_options.hpp>
#include "gdal/gdal_priv.h"
#include "gdal/ogr_api.h"

using namespace std;
namespace po = boost::program_options;


CPLErr ReadHistogram( GDALRasterBand *poBand )
 {
     int        nXBlocks, nYBlocks, nXBlockSize, nYBlockSize;
     int        iXBlock, iYBlock;
     GByte      *pabyData;
     CPLAssert( poBand->GetRasterDataType() == GDT_Byte );
     poBand->GetBlockSize( &nXBlockSize, &nYBlockSize );
     nXBlocks = (poBand->GetXSize() + nXBlockSize - 1) / nXBlockSize;
     nYBlocks = (poBand->GetYSize() + nYBlockSize - 1) / nYBlockSize;
     pabyData = (GByte *) CPLMalloc(nXBlockSize * nYBlockSize);
     for( iYBlock = 0; iYBlock < nYBlocks; iYBlock++ )
     {
         for( iXBlock = 0; iXBlock < nXBlocks; iXBlock++ )
         {
             int        nXValid, nYValid;
             poBand->ReadBlock( iXBlock, iYBlock, pabyData );
             // Compute the portion of the block that is valid
             // for partial edge blocks.
             if( (iXBlock+1) * nXBlockSize > poBand->GetXSize() )
                 nXValid = poBand->GetXSize() - iXBlock * nXBlockSize;
             else
                 nXValid = nXBlockSize;
             if( (iYBlock+1) * nYBlockSize > poBand->GetYSize() )
                 nYValid = poBand->GetYSize() - iYBlock * nYBlockSize;
             else
                 nYValid = nYBlockSize;
             // Collect the histogram counts.
             /*             for( int iY = 0; iY < nYValid; iY++ )
             {
                 for( int iX = 0; iX < nXValid; iX++ )
                 {
                     //panHistogram[pabyData[iX + iY * nXBlockSize]] += 1;
                 }
             }
             */
         }
     }
     CPLFree(pabyData);
 }



template<typename T>
CPLErr ReadWriteTransform( GDALRasterBand *poBand, GDALRasterBand *outBand,
                           T transform )
 {
     int        nXBlocks, nYBlocks, nXBlockSize, nYBlockSize;
     int        iXBlock, iYBlock;
     GByte      *pabyData;
     CPLAssert( poBand->GetRasterDataType() == GDT_Byte );
     poBand->GetBlockSize( &nXBlockSize, &nYBlockSize );
     nXBlocks = (poBand->GetXSize() + nXBlockSize - 1) / nXBlockSize;
     nYBlocks = (poBand->GetYSize() + nYBlockSize - 1) / nYBlockSize;
     pabyData = (GByte *) CPLMalloc(nXBlockSize * nYBlockSize);
     GByte* outData = (GByte *) CPLMalloc(nXBlockSize*nYBlockSize);

     for( iYBlock = 0; iYBlock < nYBlocks; iYBlock++ )
     {
         for( iXBlock = 0; iXBlock < nXBlocks; iXBlock++ )
         {
             int        nXValid, nYValid;
             poBand->ReadBlock( iXBlock, iYBlock, pabyData );
             // Compute the portion of the block that is valid
             // for partial edge blocks.
             if( (iXBlock+1) * nXBlockSize > poBand->GetXSize() )
                 nXValid = poBand->GetXSize() - iXBlock * nXBlockSize;
             else
                 nXValid = nXBlockSize;
             if( (iYBlock+1) * nYBlockSize > poBand->GetYSize() )
                 nYValid = poBand->GetYSize() - iYBlock * nYBlockSize;
             else
                 nYValid = nYBlockSize;
             
             transform(pabyData, outData, nXValid, nYValid);

             // Collect the histogram counts.
             /*             for( int iY = 0; iY < nYValid; iY++ )
             {
                 for( int iX = 0; iX < nXValid; iX++ )
                 {
                     //panHistogram[pabyData[iX + iY * nXBlockSize]] += 1;
                 }
             }
             */
             outBand->WriteBlock( iXBlock, iYBlock, outData );
         }
     }
     CPLFree(outData);
     CPLFree(pabyData);
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
        ("in", po::value<vector<string>>(),"file to read")
        ;

    po::variables_map vm;
    auto parsed_options=po::parse_command_line(argc,argv,desc);
    po::store(parsed_options, vm);
    po::notify(vm);

    if (vm.count("help")) {
        cout << desc << endl;
        return 1;
    }

    std::string filename;
    if (vm.count("in")) {
        filename = vm["in"].as<vector<string>>()[0];
    } else {
        cout << "Use --in to include a filename." << endl;
    }

    OGRRegisterAll();
    GDALAllRegister();
    GDALDataset *poDataset = static_cast<GDALDataset*>(
                             GDALOpen(filename.c_str(),GA_ReadOnly));
    if ( poDataset == NULL ) {
       cout << "Cannot open dataset" << endl;
       return(1);
    }

    cout << "Driver: " <<
            poDataset->GetDriver()->GetDescription() << "/"<<
            poDataset->GetDriver()->GetMetadataItem( GDAL_DMD_LONGNAME )
            << endl;

    cout << "Size is " <<
            poDataset->GetRasterXSize()<< poDataset->GetRasterYSize() <<" "<<
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

    GDALRasterBand* raster_band = poDataset->GetRasterBand(1);
    ReadHistogram(raster_band);

    GDALClose(poDataset);
    return 0;
}
