# This looks at yearly corn measurements.
library("gstat")
library("lattice")


corn.table.year<- function(year=1993) {
  # Read the corn data. Written with these commands:
  # for yr in `seq 1988 2001`; do python corn_planting.py --year $yr > corn${yr}.csv; done
  # grep -h -v fips corn[1-2]*.csv > z.csv
  # head -1 corn1988.csv > z.txt
  # cat z.txt z.csv > corn_fits.csv
  tabs<-read.table("corn_fits.csv",header=TRUE, as.is=seq(2,10), sep=",",
                   colClasses=c("factor","numeric","numeric","numeric","numeric","numeric",
                                "numeric","numeric","numeric","numeric"))
  yr.col <- tabs$year
  pick.year<-yr.col==year
  df<-data.frame(lat=tabs$lat[pick.year], long=tabs$long[pick.year], mid=tabs$mid[pick.year],
                  spread=tabs$spread[pick.year])
  return(df)
}


fit.corn.lats <- function(rust) {
  lats<-rust$lat
  days<-rust$mid
  latm<-lm(days ~ lats)
  #summary(latm)
  return(latm)
}


corn.anova<-function() {
  # This gives a linear fit to every year.
  # Compare with rust_obs.R:years.anova
  lots.fits<-list()
  for (yr in seq(1988,2001)) {
    lots.fits[[yr]]<-fit.corn.lats(corn.table.year(yr))
  }
  return(lots.fits)
}


corn.rust.compare<-function(corn.fits, lots.fits) {
  # Make a tukey plot of several regression residuals together.
  vals=c()
  yrs=c()
  which=c()
  for (yr in seq(1988,2001)) {
    nvals<-bp(lots.fits[[yr]])
    vals<-c(vals,nvals)
    yrs<-c(yrs,rep(yr,length(nvals)))
    which<-c(which,rep("rust",length(nvals)))
    
    nvals<-bp(lots.fits[[yr]])
    vals<-c(vals,nvals)
    yrs<-c(yrs,rep(yr,length(nvals)))
    which<-c(which,rep("corn",length(nvals)))
  }
  df<-data.frame(v=vals, y=yrs)
  boxplot(v~y+which, df, outline=FALSE, main="Comparison of Corn Planting and Rust Spread 1988-2001",
          xlab="Year of Observation", ylab="Days per Degree of Latitude",
          col=c('red','gold'))
}


# krige the corn onto the rust counties.
test.krige<-function() {
  # latitude 25 to 49
  # longitude 110 to 80
  c93<-corn.table.year(1993)
  coordinates(c93)=~long+lat
  xyplot(mid ~ lat, as.data.frame(c93))

  source('nogeo.R')
  r93<-clean.table.year(1993,F,F)
  coordinates(r93)= ~long+lat
  
  plot(variogram(mid ~ lat, c93, cloud=T, cutoff=20))
  # fit.variogram does not recognize the cloud version. It needs a cloud=F version.
  v<-variogram(mid ~ lat, c93, cutoff=20)
  v.fit<-fit.variogram(v, vgm(psill=35, model="Sph", range=20, nugget=5))
  kr<-krige(mid~lat, c93, r93, v.fit)
  # kr<-krige(formula=mid~lat, locations=c93, newdata=r93, v.fit)

  gr<-GridTopology(c(-110,25),c(1,1),c(40,24))
  spatial_grid<-SpatialGrid(gr, CRS("+proj=longlat ellps=WGS84"))
  
  # this form pulls out a data frame with just that col as data
  cr=c(84,29,258,6,555)
  spplot(r93['day'], main="rust day", col.regions=cr)
  spplot(c93['mid'], main="corn plant day", col.regions=cr)
  spplot(kr["var1.pred"],main="kriging prediction", col.regions=cr) 
  spplot(kr["var1.var"], main="kriging variance", col.regions=cr)
  r93$corn<-kr$var1.pred
  
  lat.fit<-lm(day~lat, r93)
  corn.fit<-lm(day~corn, r93)
  summary(lat.fit)
  summary(corn.fit)
  
  p93<-r93
  p93$latfit<-lat.fit$residuals
  p93$cornfit<-corn.fit$residuals
  
  mr=par()$mfrow
  par(mfrow=c(1,2))
  spplot(p93["latfit"], col.regions=cr, main="Rust Fit to Latitude")
  spplot(p93["cornfit"], col.regions=cr, main="Rust Fit to Corn Planting")
  par(mfrow=mr)
  
}


gearys.corn<-function(rust, plot=F) {
  # Conversion from SpatialPointsDataFrame to geodata. It can be done.
  df93<-data.frame(coords=coordinates(p93), data=p93$cornfit)
  rust<-as.geodata(df93, coords.col=c("coords.long", "coords.lat"), data.col=c("data"))
  
  coords<-rust$coords
  ids<-row.names(as(rust,"geodata"))
  # This uses the nearest neighbors
  rust_kn4<-knn2nb(knearneigh(coords,4), row.names=ids)
  # This is an arbitrary distance. It leads to empty neighbor sets.
  #r93_kd<-dnearneigh(coords, d1=0, d2=5, row.names=ids)
  if (plot) {
    points(rust) # If you want to check out a plot.
    plot(rust_kn4, coords, add=T)
  }
  nbq_wb<-nb2listw(rust_kn4)
  mt<-moran.test(rust$data, listw=nbq_wb)
  gc<-geary.test(rust$data, listw=nbq_wb)
  return(list(Moran=mt, Geary=gc))
}

