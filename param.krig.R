# The goal of this work is to do a parameterized kriging on rust spread.
# We want to figure out how many effective degress of freedom there are.
library(fields)
source("corn_yearly.R")

corn.krig<-function() {
  c93<-corn.table.year(1993)
  fit<-Krig(cbind(c93$long, c93$lat), c93$mid, Covariance="Matern", Distance="rdist.earth")
  summary(fit)
  
  pdf(width=6,height=5.5, file="corn_planting_day_of_year.pdf")
  surface(fit, type="I", main="Corn Planting Day of the Year", xlab="Longitude",ylab="Latitude", extrap=TRUE)
  US(add=TRUE, extrap=TRUE)
  points(fit$x)
  dev.off()
  
  # The standard error ranges from 6.4 to above 7.4, which is in days.
  out.p<-predict.surface.se(fit)
  pdf(width=6,height=5.5, file="corn_planting_day_of_year_se.pdf")
  surface(out.p, type="C", main="Standard Error on Corn Planting",xlab="Longitude",ylab="Latitude")
  dev.off()
  
}


read.year<-function(year) {
  # table headings: lat long day stage severity prevalence geoid
  r<-clean.table.year(year,F,F)
  # Cut out upper left-hand corner b/c elevation changes greatly and infections are local.
  r<-r[r$long>(-103) || r$lat<37,] # Notice comma at the end, so you get all the columns.
  return(r)
}


rust.krig<-function()
{
  source("nogeo.R")
  r93<-read.year(1993)
  
  # Kriging options of note:
  #  m = degree of polynomial function for drift. 2=linear. 3=parabolic.
  # Adding a Z of covariates is another option.
  fit<-Krig(cbind(r93$long, r93$lat), r93$day, Z=as.matrix(r93$stage), Covariance="Matern",
            Distance="rdist.earth", verbose=TRUE)
  pdf(width=7,height=10, file="rust_93_fit_summary.pdf")
  set.panel(2,2)
  plot(fit)
  set.panel()
  dev.off()
  # The surface looks like a simple south-to-north variation.
  pdf(width=6,height=5.5, file="rust_93_fit_observation.pdf")
  surface(fit, type="I", main="Rust Observation, Day of the Year", xlab="Longitude",ylab="Latitude", extrap=TRUE)
  points(fit$x)
  US(add=TRUE)
  dev.off()
  
  # Prediciton of standard error works great, as long as Z isn't specified.
  # How do you turn on Z? I need to see standard error when there are covariates.
  out.p<-predict.surface.se(fit,extrap=TRUE, Z=as.matrix(r93$stage))
  pdf(width=6,height=5.5, file="rust_93_fit_se.pdf")
  surface(out.p, type="C",main="Standard Error on Rust Observations",xlab="Longitude", ylab="Latitude")
  US(add=TRUE)
  dev.off()
}


reduce.design<-function()
{
  knot.nn<-20
  r93<-read.year(1993)
  xknots<-cover.design(cbind(r93$long, r93$lat), knot.nn)$design
  fit<-Krig(cbind(r93$long, r93$lat), r93$day, knots=xknots, Covariance="Matern", Distance="rdist.earth")
  surface(fit,type="C", extrap=TRUE)
  US(add=TRUE)
  points(fit$x)
  points( xknots, cex=2, pch="O")
  
  qqnorm( fit$residuals ); qqline( fit$residuals )
}