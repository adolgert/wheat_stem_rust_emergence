library(gstat)
library(lattice) # for xyplot


all.table.year<- function(year=1993) {
  # This reads a file that has all of the covariates.
  tabs<-read.table("first_passage.dat",header=TRUE)
  yr.col <- tabs$year
  pick.year<-yr.col==year
  df<-data.frame(lat=tabs$lat[pick.year], long=tabs$long[pick.year], day=tabs$day[pick.year],
                 geoid=tabs$geoid[pick.year])
  coordinates(df)<-c("long","lat")
  #proj4string(geo.frame)<-CRS("+proj=longlat ellps=WGS84")
  return(df)
}

clean.table.year<- function(year=1993, with.coords=T, with.proj=F) {
  # This reads a file that has all of the covariates.
  tabs<-read.table("first_covariates.dat",header=TRUE)
  yr.col <- tabs$year
  pick.year<-yr.col==year
  df<-data.frame(lat=tabs$lat[pick.year], long=tabs$long[pick.year], day=tabs$day[pick.year],
                 stage=tabs$stage[pick.year], severity=tabs$severity[pick.year],
                 prevalence=tabs$prevalence[pick.year], geoid=tabs$geoid[pick.year])
  if (with.coords) {
    coordinates(df)<-c("long","lat")
  }
  if (with.proj) {
    proj4string(geo.frame)<-CRS("+proj=longlat ellps=WGS84")
  }
  return(df)
}

# county coords come from
# import county
# county.county_coords('county_coords.dat')
all.county.coords<-function() {
  tabs<-read.table("county_coords.dat", header=TRUE)
  df<-data.frame(lat=tabs$INTPTLAT10, long=tabs$INTPTLON10, fips=tabs$GEOID10)
  #coordinates(df)<-c("long","lat")
}


gstat.vario<-function(rust, toplot=F) {
  v<-variogram(day ~ lat, data=rust, cloud=T) #option="cloud")
  if (toplot) {
    plot(v,cex=1.5,pch=19,col=1)
  }
  return(v)
}


gvario.combine<-function(v1,v2) {
  v1<-as.data.frame(v1)
  v2<-as.data.frame(v2)
  v<-data.frame(dist=c(v1$dist,v2$dist), gamma=c(v1$gamma,v2$gamma), dir.hor=c(v1$dir.hor,v2$dir.hor),
                dir.ver=c(v1$dir.ver,v2$dir.ver), id=c(v1$id,v2$id))
                #left=c(v1$left,v2$left), right=c(v1$right,v2$right))
  return(v)
}


combine.varios<-function() {
  v<-gstat.vario(clean.table.year(1988))
  for (yr in seq(1989,2001)) {
    v<-gvario.combine(v,gstat.vario(clean.table.year(yr)))
  }
  class(v)<-c("gstatVariogram", "data.frame")
  return(v)
}


gvario.fit<-function(v) {
  v.fit<-fit.variogram(v, vgm(100, "Sph", 12, 10))
  return(v.fit)
}


# I was trying to get a variogram by assembling multiple years, but
# this function takes the year with the most points and uses its
# variogram.
get.variogram<-function() {
  v<-gstat.vario(all.table.year(1991))
  class(v)<-c("gstatVariogram", "data.frame")
  v.fit<-fit.variogram(v, vgm(100, "Sph", 12, 10))
  return(v.fit)
}

read.counties <- function() {
  counties<-readOGR(get.config("continental_county"), layer="continental")
  return(counties)
}


trying <- function() {
  clean91<-clean.table.year(1991)
  proj4string(clean91)<-CRS("+proj=longlat ellps=WGS84")
  target<-all.county.coords()
  coordinates(target)<-c("long","lat")
  proj4string(target)<-CRS("+proj=longlat ellps=WGS84")
  v.fit<-get.variogram()
  proj4string(v.fit)<-CRS("+proj=longlat ellps=WGS84")
  day=clean91$day
  lat=clean$lat
  lz.ok<-krige(day ~ lat, data=data,locations=clean91$coords, newdata=target, model=v.fit)
}

