#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Polygon_2.h>
#include <iostream>

typedef CGAL::Exact_predicates_inexact_constructions_kernel K;
typedef K::Point_2 Point;
typedef CGAL::Polygon_2<K> Polygon_2;
using std::cout; using std::endl;


int main()
{
  Point points[] = { Point(0,0), Point(5.1,0), Point(1,1), Point(0.5,6)};
  Polygon_2 pgn(points, points+4);

  // check if the polygon is simple.
  cout << "The polygon is " <<
    (pgn.is_simple() ? "" : "not ") << "simple." << endl;

  // check if the polygon is convex
  cout << "The polygon is " <<
    (pgn.is_convex() ? "" : "not ") << "convex." << endl;

  return 0;
}


#include <CGAL/Cartesian.h>
#include <CGAL/centroid.h>

#include <list>
#include <iostream>

typedef double               FT;
typedef CGAL::Cartesian<FT>  K;
typedef K::Point_2           Point_2;
typedef K::Point_3           Point_3;
typedef K::Triangle_3        Triangle_3;

int main()
{
  // centroid of 2D points
  std::list<Point_2> points_2;
  points_2.push_back(Point_2(1.0, 0.0));
  points_2.push_back(Point_2(2.0, 2.0));
  points_2.push_back(Point_2(3.0, 5.0));
  Point_2 c2 = CGAL::centroid(points_2.begin(), points_2.end(),CGAL::Dimension_tag<0>());
  std::cout << c2 << std::endl;

  // centroid of 3D points
  std::list<Point_3> points_3;
  points_3.push_back(Point_3(1.0, 0.0, 0.5));
  points_3.push_back(Point_3(2.0, 2.0, 1.2));
  points_3.push_back(Point_3(3.0, 5.0, 4.5));
  Point_3 c3 = CGAL::centroid(points_3.begin(), points_3.end(),CGAL::Dimension_tag<0>());
  std::cout << c3 << std::endl;

  // centroid of 3D triangles
  std::list<Triangle_3> triangles_3;
  Point_3 p(1.0, 0.0, 0.0);
  Point_3 q(1.0, 2.0, 0.0);
  Point_3 r(0.0, 1.0, 3.0);
  Point_3 s(0.0, 2.0, 5.0);
  triangles_3.push_back(Triangle_3(p,q,r));
  triangles_3.push_back(Triangle_3(p,q,s));
  c3 = CGAL::centroid(triangles_3.begin(), triangles_3.end(),CGAL::Dimension_tag<2>());
  std::cout << c3 << std::endl;

  return 0;
}
