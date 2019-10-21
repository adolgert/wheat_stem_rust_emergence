from PIL import Image
import logging
import numpy as np
from collections import defaultdict
import county



logger=logging.getLogger(__file__)

#http://sbr.ipmpipe.org/cgi-bin/sbr/public.cgi
#http://sbr.ipmpipe.org/cgi-bin/sbr/county_info.cgi?date=2007-08-01&order_by=date
#http://sbr.ipmpipe.org/cgi-bin/sbr/sbr_map.cgi?date=2012-07-31&overlay=-99&map_type_id=5&width=1024&height=768&pest=soybean_rust&host=All%20Legumes/Kudzu&language_sel=1&image=/dy_images/sbr_13437380456604.png&minx=-126.248076923077&miny=10.2242991452991&maxx=-64.7519230769231&maxy=57.5080085470085&projection=init=epsg:4326&link_category_html=&management_toolbox_html=&HTML_COMMENTARY=&HTML_Educational%20Resources=&HTML_Hurricane%20Animations=&HTML_ID/Scouting%20Tools=&HTML_IPM%20PIPE%20General%20Site=&HTML_Management=&HTML_Not%20sure%20if%20it%20is%20Rust?=&HTML_Observation%20Animations=&HTML_Other%20SBR%20Sites=&HTML_Partners=&HTML_Professional%20Societies=&HTML_Soybean%20Rust:%20Scout%20Before%20you%20Spray=&HTML_Website%20Tutorial=&zoom=0&map_x=512&map_y=384&zoom_box_minx=&zoom_box_miny=&zoom_box_maxx=&zoom_box_maxy=&large_map=1


def xy_to_latlong(coord, limits, dims):
    '''
    coord is the pixel coordinate.
    limits is min/max in x and y. [0] is x [0][0] is xmin [0][1] is xmax
    dims is the width and height.
    '''
    latlong=[0,0]

    cxy=(limits[0][1]-limits[0][0])/dims[0]
    latlong[1]=limits[0][0] + cxy*coord[0]

    cxy=(limits[1][1]-limits[1][0])/dims[1]
    latlong[0]=limits[1][1] - cxy*coord[1]

    return latlong



def latlong_to_xy(coord, limits, dims):
    pixel=[0,0]

    pixel[0]=(coord[1]-limits[0][0])*dims[0]/(limits[0][1]-limits[0][0])
    pixel[1]=-(coord[0]-limits[1][1])*dims[1]/(limits[1][1]-limits[1][0])
    return pixel



def pixel_counties():
    pass
    # open county file
    # get lat,long
    


def one_image(name, county_info):
    # PIL pixels define (0,0) as the upper-left corner.
    # Javascript does the same.
    # The width (1024) goes with x, which is longitude.
    limits=[[-126.248076923077,-64.7519230769231],[10.2242991452991,57.5080085470085]]
    dims=[1024,768]
    im=Image.open(name)

    colors=defaultdict(int)
    altcolors=defaultdict(lambda: defaultdict(int))

    prescol={
        (255, 255, 255) : 0,
        (0, 255, 0) : 1,
        (255, 230, 230) : 2,
        (255, 0, 0) : 3,
        (0, 0, 0) : 0
        }

    results=dict()
    for ckey in county_info.keys():
        ci=county_info[ckey]
        fips=ci['GEOID10']
        lat=float(ci['INTPTLAT10'])
        lon=float(ci['INTPTLON10'])
        name=ci['NAME10']
        statefips=ci['STATEFP10']

        pixel=latlong_to_xy((lat,lon), limits, dims)
        #logging.debug('pixel is %s' % str(pixel))
        try:
            color=im.getpixel(tuple(pixel))
            if color==(0,0,0):
                bds=ci['bounds']
                ul=im.getpixel((bds[0], bds[3]))
                lr=im.getpixel((bds[2], bds[1]))
                logger.debug('%s %s' % (str(ul), str(lr)))
                for i in np.arange(ul[0], lr[0], 1):
                    for j in np.arange(ul[1], lr[1], 1):
                        val=im.getpixel((i,j))
                        altcolors[fips][val]+=1
                        logger.debug('i %d j %d %s' % (i,j,str(val)))
            colors[color]+=1
            
            results[fips]={'name' : name, 'statefips' : statefips,
                           'presence' : prescol[color] }
        except IndexError:
            pass
            #logger.debug("County %s in %s not found" % (name,statefips))
        
    return results, colors, altcolors



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    counties=county.county_basics()
    results, colors, altcolors=one_image('sbr/2007_01.png', counties)
    for k in results.keys():
        results[k]['presence']=list()

    for mon in range(1,13):
        fname='sbr/2007_%02d.png' % mon
        res, colors, altcolors=one_image(fname, counties)
        for k in res.keys():
            results[k]['presence'].append(res[k]['presence'])

    for k in sorted(res.keys()):
        p=results[k]['presence']
        print(k, results[k]['name'], results[k]['statefips'],
              ', '.join([str(x) for x in p]))
