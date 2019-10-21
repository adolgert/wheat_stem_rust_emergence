#ifndef _RASTER_GEOMETRY_HPP_
#define _RASTER_GEOMETRY_HPP_ 1

#include <algorithm>
#include <boost/array.hpp>
#include "gdal/gdal_priv.h"
#include "gdal/ogr_api.h"


namespace imaging {

    typedef boost::array<size_t,2> face_id_t;
    typedef boost::array<size_t,2> block_id_t;
    typedef boost::array<double,2> xy_t;
    typedef boost::array<xy_t,2> xy_bounds_t;

    
    class raster_storage {
        boost::array<size_t,2> _blocking;
    public:
        raster_storage(boost::array<size_t,2> blocking)
            : _blocking(blocking) {}
        
    };

    template <class Value>
    class xy_iter
        : public boost::iterator_facade<xy_iter<Value>,
                                        Value,
                                        boost::forward_traversal_tag
                                        >
    {
        boost::array<block_id_t,2> _bounds;
        block_id_t _xy;
        bool _ordering;
    public:
        xy_iter() {}
        explicit xy_iter(boost::array<block_id_t,2> bounds,
                             bool ordering)
            : _bounds(bounds), _ordering(ordering), _xy(bounds[0])
        { }
        explicit xy_iter(boost::array<block_id_t,2> bounds,
                             bool ordering,
                             Value start)
            : _bounds(bounds), _ordering(ordering), _xy(start)
        { }
        xy_iter<Value> last() {
            int fast= _ordering ? 1 : 0;
            int slow=fast-1;
            block_id_t xy_end;
            xy_end[fast]=_bounds[0][fast];
            xy_end[slow]=_bounds[1][slow];
            return xy_iter<Value>(_bounds, _ordering, xy_end);
        }
    private:
        friend class boost::iterator_core_access;
        void increment() {
            int fast= _ordering ? 1 : 0;
            int slow=fast-1;
            
            _xy[fast]++;
            if (_xy[fast]==_bounds[fast][1]) {
                _xy[fast]=_bounds[fast][0];
                _xy[slow]++;
            }
        }
        template <class OtherValue>
        bool equal(xy_iter<OtherValue> const& other) const
        {
            return _xy == other._xy;
        }
        Value& dereference() const { return _xy; }
    };
    typedef xy_iter<block_id_t> xy_iterator;
    typedef xy_iter<block_id_t const> xy_const_iterator;



    boost::array<xy_const_iterator,2>
    make_xy_const_iterator( boost::array<block_id_t,2> bounds, bool ordering,
                      const block_id_t& cur)
    {
        boost::array<xy_const_iterator,2> iters;
        iters[0]=xy_const_iterator(bounds, ordering, cur);
        iters[1]=iters[0].last();
        return iters;
    }



    class xy_blocked_iterator
        : public boost::iterator_facade<xy_blocked_iterator,
                                        face_id_t const,
                                        boost::forward_traversal_tag
                                        >
    {
        boost::array<face_id_t,2> _bounds;
        boost::array<size_t,2> _blocking;
        boost::array<xy_const_iterator,2> _block_iter;
        boost::array<xy_const_iterator,2> _face_iter;
        boost::array<bool,2> _ordering;
        face_id_t _face;
    public:
        xy_blocked_iterator() {}
        explicit xy_blocked_iterator(boost::array<face_id_t,2> bounds,
                                     boost::array<size_t,2> blocking,
                                     boost::array<bool,2> ordering)
        {
            face_id_t block;
            block[0]=bounds[0][0]/_blocking[0];
            block[1]=bounds[0][1]/_blocking[1];
            init(bounds,blocking,ordering,block);
        }

        explicit xy_blocked_iterator(boost::array<face_id_t,2> bounds,
                                     boost::array<size_t,2> blocking,
                                     boost::array<bool,2> ordering,
                                     face_id_t block)
        {
            init(bounds,blocking,ordering,block);
        }
        
        xy_blocked_iterator last() {
            return xy_blocked_iterator(_bounds, _blocking,
                                       _ordering, *_block_iter[1]);
        }
     private:
        friend class boost::iterator_core_access;
        void increment() {
            _face_iter[0]++;
            if (_face_iter[0] == _face_iter[1]) {
                _block_iter[0]++;
                _face_iter = new_sub_block(*_block_iter[0]);
            }
            _face=*(_face_iter[0]);
        }
        bool equal(xy_blocked_iterator const& other) const {
            return _face == other._face;
        }
        face_id_t const& dereference() const { return _face; }

        boost::array<xy_const_iterator,2>
        new_sub_block(const block_id_t& block) {
            boost::array<face_id_t,2> block_xy;
            for (int bdim=0; bdim<2; bdim++) {
                block_xy[0][bdim]=block[bdim]*_blocking[bdim];
                block_xy[1][bdim]=(block[bdim]+1)*_blocking[bdim];
            }

            boost::array<face_id_t,2> in_block;
            for (int idim=0; idim<2; idim++) {
                in_block[0][idim]=std::max(_bounds[0][idim],block_xy[0][idim]);
                in_block[1][idim]=std::min(_bounds[1][idim],block_xy[1][idim]);
            }
            return make_xy_const_iterator(in_block,_ordering[1], in_block[0]);
        }

        void init(boost::array<face_id_t,2> bounds,
                                     boost::array<size_t,2> blocking,
                                     boost::array<bool,2> ordering,
                                     face_id_t block)
        {
            _bounds=bounds;
            _blocking=blocking;
            _ordering=ordering;

            boost::array<block_id_t,2> block_bounds;
            block_bounds[0][0]=bounds[0][0]/_blocking[0];
            block_bounds[0][1]=bounds[0][1]/_blocking[1];
            block_bounds[1][0]=bounds[1][0]/_blocking[0];
            block_bounds[1][1]=bounds[1][1]/_blocking[1];
            _block_iter=make_xy_const_iterator(block_bounds,_ordering[0],block);
            _face_iter = new_sub_block(*_block_iter[0]);
            _face=*_face_iter[0];
        }
    };



    boost::array<xy_blocked_iterator,2>
    make_xy_blocked_iterator( boost::array<block_id_t,2> bounds,
                              block_id_t blocking,
                              bool ordering )
    {
        int fast= ordering ? 1 : 0;
        int slow=fast-1;
        block_id_t start;
        start[0]=bounds[0][0];
        start[1]=bounds[0][1];
        block_id_t finish;
        finish[fast]=bounds[0][fast];
        finish[slow]=bounds[1][slow];

        boost::array<bool,2> order_both;
        order_both[0]=ordering;
        order_both[1]=ordering;
        
        boost::array<xy_blocked_iterator,2> iters;
        iters[0]=xy_blocked_iterator(bounds, blocking, order_both);
        iters[1]=iters[0].last();
            //xy_blocked_iterator(bounds, blocking, finish, order_both);
        return iters;
    }



    class raster_face {
        face_id_t _id;
    public:
        raster_face() {}
        explicit raster_face(const face_id_t& id) : _id(id) {}
        bool operator==(const raster_face& other) const {
            return _id==other._id;
        }
    };



    template<class ITER>
    class face_iterator
        : public boost::iterator_facade<face_iterator<ITER>,
                                        raster_face,
                                        boost::forward_traversal_tag
                                        >
    {
        ITER _iter;
        raster_face _face;

    public:
        face_iterator() {}
        explicit face_iterator(ITER iter)
            : _iter(iter)
        {
            _face=raster_face(*_iter);
        }

    private:
        friend class boost::iterator_core_access;
        void increment() {
            _iter++;
            _face=raster_face(*_iter);
        }
        bool equal(face_iterator const& other) const {
            return _face==other._face;
        }
        raster_face& dereference() { return _face; }
    };



    class raster_faces {
        OGRSpatialReference _srs;
        double _geo_xform[6];
        boost::array<face_id_t,2> _bounds;
        boost::array<size_t,2> _blocking;
    public:
        typedef face_iterator<xy_blocked_iterator> iterator;

        raster_faces(GDALRasterBand* band)
        {
            GDALDataset* ds = band->GetDataset();
            const char* proj = ds->GetProjectionRef();
            _srs.importFromWkt(const_cast<char**>(&proj));

            bounds_from_raster_band(band);
        }

        raster_faces(GDALRasterBand* band, const char* proj4)
        {
            _srs.importFromProj4( proj4 );
            bounds_from_raster_band(band);
        }

        boost::array<iterator,2> forward() {
            boost::array<xy_blocked_iterator,2> blocked =
                make_xy_blocked_iterator(_bounds, _blocking, true);
            boost::array<iterator,2> iters;
            iters[0]=iterator(blocked[0]);
            iters[1]=iterator(blocked[1]);
        }
        
        

    private:
        void bounds_from_raster_band(GDALRasterBand* band) {
            GDALDataset* ds = band->GetDataset();
            ds->GetGeoTransform(_geo_xform);
            _bounds[0][0]=0;
            _bounds[0][1]=0;
            _bounds[1][0]=band->GetXSize();
            _bounds[1][1]=band->GetYSize();
            int iblock[2];
            band->GetBlockSize( &iblock[0], &iblock[1] );
            _blocking[0]=iblock[0];
            _blocking[1]=iblock[1];
        }
        
    };



    class raster_geometry {
        OGRSpatialReference _srs;
        double _geo_xform[6];
        size_t _bounds[2];

    public:
        raster_geometry(GDALRasterBand* band) {
            GDALDataset* ds = band->GetDataset();
            const char* proj = ds->GetProjectionRef();
            _srs.importFromWkt(const_cast<char**>(&proj));

            ds->GetGeoTransform(_geo_xform);

            _bounds[0]=band->GetXSize();
            _bounds[1]=band->GetYSize();
        }
    };

}

#endif // _RASTER_GEOMETRY_HPP_
