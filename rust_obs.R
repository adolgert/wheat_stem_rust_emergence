library(geoR)
library(Rcmdr)
library(geoRglm)
library(arm) # gives se.coef
library(rgdal)
library(maptools)
#library(spplot)
library(spdep)
source("project_config.R")

maybe.needed.for.rgdal<-function() {
  Sys.setenv(LD_LIBRARY_PATH="/usr/local/lib:/opt/lib:/usr/local/grass-6.4.2/lib:/usr/lib/x86_64-linux-gnu")
  library(rgdal)
}

# The file first_passage.dat comes from
# python county.py --firstr --out first_passage.dat
# The coords are 0-lat 1-long.
load.rust <- function(all_years=TRUE) {
  if (all_years) {
    rust<-read.geodata(file="first_passage.dat",header=TRUE,coords.col=c(2,1),
                       data.col=4, data.names="day", colClasses=c("numeric","numeric","factor","integer"))
    rustjit <- rust
    rustjit$coords <- jitterDupCoords(rust$coords, max=0.1, min=0.02)
    return(rustjit)
  } else {
    rust<-read.geodata(file="first_passage.dat",header=TRUE,coords.col=c(2,1,3),
                      data.col=4, data.names="day", colClasses=c("numeric","numeric","integer","integer"))
    return(rust)
  }
}



just.year <- function(rust,year=1993) {
  yr.col <- rust$coords[,3]
  pick.year<-yr.col==year
  just.year<-list(coords=rust$coords[pick.year,1:2],data=rust$data[pick.year],
                  other=rust$other)
  return(just.year)
}


just.table.year<- function(year=1993) {
  # This picks out the year from the file before converting to a geodata.
  # It seems to create a more correct geodata than reading the file directly and modifying it.
  tabs<-read.table("first_passage.dat",header=TRUE)
  yr.col <- tabs$year
  pick.year<-yr.col==year
  df<-data.frame(lat=tabs$lat[pick.year], long=tabs$long[pick.year], day=tabs$day[pick.year])
  geo.frame<-as.geodata(df,coords.col=c("long","lat"), data.col=c("day"))
  return(geo.frame)
}



clean.table.year<- function(year=1993) {
  # This reads a file that has all of the covariates.
  tabs<-read.table("first_covariates.dat",header=TRUE)
  yr.col <- tabs$year
  pick.year<-yr.col==year
  df<-data.frame(lat=tabs$lat[pick.year], long=tabs$long[pick.year], day=tabs$day[pick.year],
                 stage=tabs$stage[pick.year], severity=tabs$severity[pick.year],
                 prevalence=tabs$prevalence[pick.year], geoid=tabs$geoid[pick.year])
  geo.frame<-as.geodata(df,coords.col=c("long","lat"), data.col=c("day"),
                        covar.col=c("stage","severity","prevalence"))
  #proj4string(geo.frame)<-CRS("+proj=longlat ellps=WGS84")
  return(geo.frame)
}



read.counties <- function() {
  counties<-readOGR(get.config("continental_county"), layer="continental")
  return(counties)
}


years.anova<-function() {
  rusty<-load.rust(FALSE)
  lots.fits<-list()
  for (yr in seq(1988,2001)) {
    rust.yr<-just.year(rusty, yr)
    lots.fits[[yr]]<-fit.lats(rust.yr)
  }
  return(lots.fits)
}



fit.lats <- function(rust) {
  lats<-rust$coords[,2]
  days<-rust$data
  latm<-lm(days ~ lats)
  #summary(latm)
  return(latm)
}


set.fits <- function(rust) {
  lats<-rust$coords[,2]
  days<-rust$data
  stage<-rust$covariate[,1]
  severity<-rust$covariate[,2]
  prevalence<-rust$covariate[,3]
  res=list()
  res$lats<-lm(days ~ lats)
  res$severity<-lm(days ~ lats + severity)
  res$prevalence<-lm(days ~ lats + prevalence)
  res$stage <- lm(days ~ lats + stage)
  res$ss<- lm(days ~ lats + stage + severity)
  #summary(latm)
  return(res)
}


compare.residuals<-function(res1, res2) {
  mfrow=par()$mfrow
  par(mfrow=c(1,2))
  hist(res1,20, main="Residuals on Fit to Latitude")
  hist(res2,20,main="Residuals on Fit to Lat and Severity")
  par(mfrow=mfrow)
}

spatial.with.residuals<-function(original, fit) {
  # spatial.with.residuals(r93, <one of the fits>)
  copy<-original
  copy$data<-original$data-fit$fitted.values
  mfrow<-par()$mfrow
  par(mfrow=c(1,2))
  points(original, ylab="lat", xlab="long", col=gray(seq(1,.1, l=8)), main="Original Values")
  points(copy, ylab="lat", xlab="long", col=gray(seq(1,.1, l=8)), main="After Fit")
  par(mfrow=mfrow)  
}


examine.fit <- function(rustfit) {
  plot(rustfit)
  hist(residuals(rustfit),breaks=20)
}



norm.from.fit <- function(rust,fit) {
  rustfit <- rust
  rustfit$data <- rust$data-fitted(fit)
  return(rustfit)
}


plot.vario.yr <- function(rust,yr) {
  r.yr<-just.year(rust,yr)
  fit.yr<-fit.lats(r.yr)
  norm.yr<-norm.from.fit(r.yr, fit.yr)
  bin1<-variog(norm.yr, uvec=seq(0, 40, l=11))
  return(bin1)
}

vario.fitted <- function(rust) {
  lats<-rust$coords[,2]
  days<-rust$data
  fit<-lm(days ~ lats)
  copy<-rust
  copy$data<-rust$data-fit$fitted.values
  bin1<-variog(copy, uvec=seq(0,40, l=11), option="cloud", max.dist=40)
  return(bin1)
}


combine.vario<-function(var1,var2) {
  # These should be computed with option="cloud
  var3<-var1
  var3$u<-c(var1$u, var2$u)
  var3$v<-c(var1$v, var2$v)
  var3$n.data=var1$n.data+var2$n.data
  return(var3)
}


sum.variograms<-function()
{
  bin1<-vario.fitted(clean.table.year(1988))
  for (yr in seq(1989,2001)) {
    bin1<-combine.vario(bin1, vario.fitted(clean.table.year(yr)))    
  }
  return(bin1)
}


gstat.vario<-function(rust, toplot=F) {
  ddf<-data.frame(long=rust$coords[,1], lat=rust$coords[,2], day=rust$data,
                  stage=rust$covariate[,1], severity=rust$covariate[,2],
                  prevalence=rust$covariate[,3])
  coordinates(ddf)<-c("long","lat")
  v<-variogram(day ~ lat, data=ddf, cloud=T) #option="cloud")
  fit.variogram(v, vgm(800, "Sph", 20, 100))
  if (toplot) {
    plot(v,cex=1.5,pch=19,col=1)
  }
  return(v)
}


gvario.combine<-function() {
  v1<-as.data.frame(gstat.vario(clean.table.year(1993)))
  v2<-as.data.frame(gstat.vario(clean.table.year(1994)))
  v<-data.frame(dist=c(v1$dist,v2$dist), gamma=c(v1$gamma,v2$gamma), dir.hor=c(v1$dir.hor,v2$dir.hor),
                dir.ver=c(v1$dir.ver,v2$dir.ver), id=c(v1$id,v2$id),
                left=c(v1$left,v2$left), right=c(v1$right,v2$right))
  return(list(v1=v1,v2=v2,v=v))
}


gearys<-function(rust, plot=F) {
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



# I need the distribution in order to 
bp <- function(fit) {
  mean=coefficients(fit)[[2]]
  stdev=se.coef(fit)[[2]]
  cnt<-100
  vals<-rnorm(cnt, mean=mean, sd=stdev)
  return(vals)
}


slopes.boxplot<-function(lots.fits) {
  boxplot(bp(lots.fits[[1988]]),bp(lots.fits[[1989]]),bp(lots.fits[[1990]]),bp(lots.fits[[1991]]),
          bp(lots.fits[[1992]]),bp(lots.fits[[1993]]),bp(lots.fits[[1994]]),bp(lots.fits[[1995]]),
          bp(lots.fits[[1996]]),bp(lots.fits[[1996]]),bp(lots.fits[[1997]]),bp(lots.fits[[1998]]),
          bp(lots.fits[[1999]]),bp(lots.fits[[2000]]),bp(lots.fits[[2001]]))
}

# Smarter way to make boxplots
slopes.try<-function(lots.fits) {
  vals=c()
  yrs=c()
  for (yr in seq(1988,2001)) {
    nvals<-bp(lots.fits[[yr]])
    vals<-c(vals,nvals)
    yrs<-c(yrs,rep(yr,length(nvals)))
  }
  df<-data.frame(v=vals, y=yrs)
  boxplot(v~y, df, outline=FALSE, main="Estimated Rate of Rust Spread 1988-2001",
          xlab="Year of Observation", ylab="Days per Degree of Latitude")
}

compare.year.slopes <- function(rustyears) {
  m1<-fit.lats(rustyear)
  m2<-fit.lats(rustyear)
  anova(m1,m2)
}

slopes.residual.plots <- function(lots.fits) {
  pmat=par()
  par(mfrow=c(4,4))
  for (yr in seq(1988,2001)) {
    hist(residuals(lots.fits[[yr]]), main=as.character(yr),xlab="days",breaks=20)
  }
  par(mfrows=pmat)
}


all.residuals<-function(lots.fits) {
  pmat=par()$mfrow
  par(mfrow=c(1,2))
  resid=c()
  for (yr in seq(1988,2001)) {
    resid=c(resid,residuals(lots.fits[[yr]]))
  }
  hist(resid,breaks=40,main="Residuals on All Years",xlab="Days")
  qqnorm(resid,main="Q-Q Plot of Residuals")
  qqline(resid)
  par(mfrow=pmat)  
}


plot.rust <- function(rust) {
  covario<-covariog(rust, uvec=c(1:30))
  plot(covario)
  scatter3d(rust$data ~ rust$coords[,1] + rust$coords[,2])
}

krige.rust <- function(rust) {
  loci <- expand.grid(seq(25,50,l=21), seq(-85,-120,l=21))
  
  kc <- krige.conv(rust, loc=loci,
                   krige=krige.control(cov.pars=c(1, .25)))
  # mapping point estimates and variances
  par.ori <- par(no.readonly = TRUE)
  par(mfrow=c(1,2), mar=c(3.5,3.5,1,0), mgp=c(1.5,.5,0))
  image(kc, main="kriging estimates")
  image(kc, val=sqrt(kc$krige.var), main="kriging std. errors")
}



rust.semivariogram <- function(rust) {
  v1 <- variog(coords=rust$coords, data=rust$data, breaks=c(seq(0,10,11)))
  v1.summary <- cbind(c(1:10), v1$v, v1$n)
  colnames(v1.summary) <- c("lag", "semi-variance", "# of pairs")
  v1.summary
  plot(v1, type = "b", main = "Variogram: rust") 
  return(v1)
}


test.example <- function() {
  rust <- load.rust(all_years=FALSE)
  r93 <- just.year(rust,1993)
  plot.rust(r93)
  krige.rust(r93)
}

