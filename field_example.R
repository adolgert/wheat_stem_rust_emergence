# a 2-d example 
# fitting a surface to ozone  
# measurements. Exponential covariance, range parameter is 20 (in miles) 

fit <- Krig(ozone$x, ozone$y, theta=20)  

summary( fit) # summary of fit 
set.panel( 2,2) 
plot(fit) # four diagnostic plots of fit  
set.panel()
surface( fit, type="C") # look at the surface 

# predict at data
predict( fit)

# predict using 7.5 effective degrees of freedom:
predict( fit, df=7.5)


# predict on a grid ( grid chosen here by defaults)
out<- predict.surface( fit)
surface( out, type="C") # option "C" our favorite

# predict at arbitrary points (10,-10) and (20, 15)
xnew<- rbind( c( 10, -10), c( 20, 15))
predict( fit, xnew)

# standard errors of prediction based on covariance model.  
predict.se( fit, xnew)

# surface of standard errors on a default grid
predict.surface.se( fit)-> out.p # this takes some time!
surface( out.p, type="C")
points( fit$x)


# Using another stationary covariance. 
# smoothness is the shape parameter for the Matern. 

fit <- Krig(ozone$x, ozone$y, Covariance="Matern", theta=10, smoothness=1.0)  
summary( fit)

#
# Roll your own: creating very simple user defined Gaussian covariance 
#

test.cov <- function(x1,x2,theta,marginal=FALSE,C=NA){
  # return marginal variance
  if( marginal) { return(rep( 1, nrow( x1)))}
  
  # find cross covariance matrix     
  temp<- exp(-(rdist(x1,x2)/theta)**2)
  if( is.na(C[1])){
    return( temp)}
  else{
    return( temp%*%C)}
} 
#
# use this and put in quadratic polynomial fixed function 


fit.flame<- Krig(flame$x, flame$y, cov.function="test.cov", m=3, theta=.5)

#
# note how range parameter is passed to Krig.   
# BTW:  GCV indicates an interpolating model (nugget variance is zero) 
# This is the content of the warning message.

# take a look ...
surface(fit.flame, type="I") 

# 
# Thin plate spline fit to ozone data using the radial 
# basis function as a generalized covariance function 
#
# p=2 is the power in the radial basis function (with a log term added for 
# even dimensions)
# If m is the degree of derivative in penalty then p=2m-d 
# where d is the dimension of x. p must be greater than 0. 
#  In the example below p = 2*2 - 2 = 2  
#

out<- Krig( ozone$x, ozone$y,cov.function="Rad.cov", 
            m=2,p=2,scale.type="range") 

# See also the Fields function Tps
# out  should be identical to  Tps( ozone$x, ozone$y)
# 

# A Knot example

data(ozone2)
y16<- ozone2$y[16,] 

# there are some missing values -- remove them 
good<- !is.na( y16)
y<- y16[good] 
x<- ozone2$lon.lat[ good,]

#
# the knots can be arbitrary but just for fun find them with a space 
# filling design. Here we select  50 from the full set of 147 points
#
xknots<- cover.design( x, 50, num.nn= 75)$design  # select 50 knot points

out<- Krig( x, y, knots=xknots,  cov.function="Exp.cov", theta=300)  
summary( out)
# note that that trA found by GCV is around 17 so 50>17  knots may be a 
# reasonable approximation to the full estimator. 
#

# the plot 
surface( out, type="C")
US( add=TRUE)
points( x, col=2)
points( xknots, cex=2, pch="O")

## A quick way to deal with too much data if you intend to smooth it anyway
##  Discretize the locations to a grid, then apply Krig 
##  to the discretized locations:
## 
CO2.approx<- as.image(RMprecip$y, x=RMprecip$x, nx=20, ny=20)

# take a look:
image.plot( CO2.approx)
# discretized data (observations averaged if in the same grid box)
# 336 locations -- down form the  full 806

# convert the image format to locations, obs and weight vectors
yd<- CO2.approx$z[CO2.approx$ind]
weights<- CO2.approx$weights[CO2.approx$ind] # takes into account averaging
xd<- CO2.approx$xd

obj<- Krig( xd, yd, weights=weights, theta=4)

# compare to the full fit:
CO2.fit=Krig( RMprecip$x, RMprecip$y, theta=4) 
surface(CO2.fit, type="C")

# A correlation model example

# fit krig surface using a mean and sd function to standardize 
# first get stats from 1987 summer Midwest O3 data set 
# Compare the function Tps to the call to Krig given above 
# fit tps surfaces to the mean and sd  points.  
# (a shortcut is being taken here just using the lon/lat coordinates) 

data(ozone2)
stats.o3<- stats( ozone2$y)
mean.o3<- Tps( ozone2$lon.lat, c( stats.o3[2,]))
sd.o3<- Tps(  ozone2$lon.lat, c( stats.o3[3,]))

#
# Now use these to fit particular day ( day 16) 
# and use great circle distance
#NOTE: there are some missing values for day 16. 

fit<- Krig( ozone2$lon.lat, y16, 
            theta=350, mean.obj=mean.o3, sd.obj=sd.o3, 
            Covariance="Matern", Distance="rdist.earth",
            smoothness=1.0,
            na.rm=TRUE) #
source("rdist.haversine.R")
fit<- Krig( ozone2$lon.lat, y16, 
            theta=350, mean.obj=mean.o3, sd.obj=sd.o3, 
            Covariance="Matern", Distance="rdist.haversine",
            smoothness=1.0,
            na.rm=TRUE)

# the finale
surface( fit, type="I")
US( add=TRUE)
points( fit$x)
title("Estimated ozone surface")

#
#
# explore some different values for the range and lambda using REML
theta <- seq( 300,400,,10)
PLL<- matrix( NA, 10,80)
# the loop 
for( k in 1:10){
  
  # call to Krig with different ranges
  # also turn off warnings for GCV search 
  # to avoid lots of messages. (not recommended in general!)
  
  PLL[k,]<- Krig( ozone2$lon.lat[good,], y16[good],
                  cov.function="stationary.cov", 
                  theta=theta[k], mean.obj=mean.o3, sd.obj=sd.o3, 
                  Covariance="Matern",smoothness=.5, 
                  Distance="rdist.earth", nstep.cv=80,
                  give.warnings=FALSE)$gcv.grid[,7]
  
  #
  # gcv.grid is the grid search output from 
  # the optimization for estimating different estimates for lambda including 
  # REML
  # default grid is equally spaced in eff.df scale ( and should the same across theta)
  #  here 
  
}

# see the 2 column of $gcv.grid to get the effective degress of freedom. 

cat( "all done", fill=TRUE)
contour( theta, 1:80, PLL)
