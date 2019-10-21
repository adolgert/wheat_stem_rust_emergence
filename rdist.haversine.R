# This is a distance computation between lat-long coordinates using the Haversine formula.
# It is meant to be used in the fields package where rdist and rdist.earth are used.
"rdist.haversine" <- function(x1, x2, miles = TRUE, R = NULL) {
    # x1 and x2 are a matrix with dims<-c(n,2).
    # We treat them as a rows of (long,lat).
    if (is.null(R)) {
        if (miles)
            R <- 3963.34
        else R <- 6378.388
    }
    if (missing(x2)) {
        # If x2 is missing, replicate what rdist.earth.R does, blindly.
        coslat1 <- cos((x1[, 2] * pi)/180)
        sinlat1 <- sin((x1[, 2] * pi)/180)
        coslon1 <- cos((x1[, 1] * pi)/180)
        sinlon1<- sin((x1[, 1] * pi)/180)
        pp <- cbind(coslat1 * coslon1, coslat1 * sinlon1, sinlat1) %*% 
            t(cbind(coslat1 * coslon1, coslat1 * sinlon1, sinlat1))
        return(R * acos(ifelse(abs(pp) > 1, 1 * sign(pp), pp)))
    }
    # We want to compute the distance between every pair in x1 and x2.
    # R is faster if we can do it as an array operation instead of a for
    # loop. We repeat elements of x1 and x2 such that, if you loop over
    # all, every pair is represented. Then do the array operation, and
    # finally convert the vector into a two-dimensional matrix.
    x1rep<-cbind(rep(x1[,1], times=dim(x2)[1]), rep(x1[,2], times=dim(x2)[1]))
    x2rep<-cbind(rep(x2[,1], each=dim(x1)[1]),  rep(x2[,2], each=dim(x1)[1]))
    res<-2*R*asin(
        sqrt(
            sin(pi*(x2rep[,2]-x1rep[,2])/360)**2 +
            cos(pi*x1rep[,2]/180)*cos(pi*x2rep[,2]/180)*sin(pi*(x2rep[,1]-x1rep[,1])/360)**2
        )        
    );
    return(array(res, dim=c(dim(x1)[1],dim(x2)[1])))
}

testing.haversine<-function(x1,x2) {
  R <- 6378.388;
  2*R*asin(
    sqrt(
      sin(0.5*(x2[2]-x1[2]))**2 +
        cos(x1[2])*cos(x2[2])*(sin(0.5*(x2[1]-x1[1]))**2)
      )
    );
}
testing.haversine2<-function(x1,x2) {
  R <- 6378.388;
  dlat<-pi*(x2[2]-x1[2])/180
  dlong<-pi*(x2[1]-x1[1])/180
  a<-sin(0.5*dlat)**2 +
    cos(x1[2])*cos(x2[2])*(sin(0.5*dlong)**2);
  return(2*R*atan2(sqrt(a), sqrt(1-a)));
}

test.haversine<-function() {
  x1<-c(-80,20);
  x2<-c(-80,22);
  given<-rdist.earth(array(x1,dim=c(1,2)),array(x2,dim=c(1,2)), miles=FALSE);
  single<-testing.haversine2(x1,x2);
  attempt<-rdist.haversine(array(x1,dim=c(1,2)),array(x2,dim=c(1,2)), miles=FALSE)
  return(list(g=given,s=single,a=attempt))
}
