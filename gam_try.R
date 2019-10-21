require(mgcv)

pixels.formatted <- function(year) {
  # Reads NDVI values for multiple pixels from a CSV file.
  # Each line is the county identifier followed by a list of 3 years of
  # bi-monthly pixels.
  year=as.character(year)
  filename=paste("pix_for_R_",year,".csv",sep="")
  cat("reading file", filename)
  
  pix=read.csv(filename, header=FALSE)
  years<-c()
  days<-c()
  for (yr in c(1999,2000,2001)) {
    yrstr=as.character(yr)
    for (mon in 1:12) {
      monstr=as.character(mon)
      for (day in c(1,16)) {
        daystr=as.character(day)
        datelike=strptime(paste(monstr,daystr,yrstr,sep="/"),"%m/%d/%y")
        years <- c(years,yr)
        days <- c(days,datelike$yday + (yr-1999)*365)
      }
    }
  }
  return(list(Id=pix[,1], Lon=pix[,2], Lat=pix[,3], Pix=pix[,c(4:ncol(pix))],Days=days))
}



# c(1:(ncol(pix)-1))

predict.one <- function(pix, days, which) {
  single.frame=data.frame( yyy = as.numeric(pix[which,]),
                            xxx=days)
  d.gam <- gam( yyy ~ s(xxx, k=20),
                gamma=1.25,
                data = single.frame)
  summary(d.gam)
  prediction.dates<-seq(from=1*365,to=2*365,length=365)
  pp <- predict(d.gam,
                newdata=data.frame(
                  xxx = prediction.dates))
  return(list(Pred=data.frame(Dates=prediction.dates,Predict=pp), Data=single.frame))
}



pixel.plot <- function(prediction.frame, single.frame) {
  par(mar=c(2,2,2,2), cex=0.5)
  plot(single.frame$xxx, single.frame$yyy,
       type="b",
       pch=19,
       cex=0.5,
       col="grey")
  lines(prediction.frame$Dates,prediction.frame$Predict,col=2)
}



find.sos <- function(prediction.frame, level) {
  # Avoid early metastable wells by skipping smaller maxima.
  # The level is the percentage of maximum at which we estimate emergence.
  pp <- prediction.frame$Predict
  prediction.dates <- prediction.frame$Dates
  
  max.at.least <- 0.4*(max(pp)-min(pp))+min(pp)
  minval=pp[[1]]
  minidx=1
  maxval=pp[[1]]
  maxidx=1
  for (i in 2:length(pp)) {
    if (pp[[i]]<minval) {
      minval<-pp[[i]]
      minidx<-i
    }
    if (maxval<pp[[i]]) {
      maxval<-pp[[i]]
      maxidx<-i
    }
    
    if (pp[[i]] < maxval - 0.05*(maxval-minval) && maxval>max.at.least) {
      break;
    }
  }
  #cat(minval, maxval, minidx, maxidx)
  
  day.estimate <- 1
  # Walk backwards to get the last time it was at 10% of max.
  for (j in maxidx:1) {
    if ( pp[[j]]< minval+level*(maxval-minval) ) {
      day.estimate <- j
      break
    }
  }
  return(prediction.dates[[day.estimate]]-365)
}



process.single <- function(pix, days, pred.idx) {
  single.pred<-predict.one(pix, days, pred.idx)
  day <- find.sos(single.pred$Pred,0.1)
  return(day)
}


process.year <- function(year,percent.max) {
  # percent.max is the percentage of total NDVI at which plants emerge.
  file.contents <- pixels.formatted(year)
  pix<-file.contents$Pix
  days<-file.contents$Days
  pixel.count<-length(file.contents$Id)
  sos <- c(0, dim=c(length(file.contents$Id)))
  
  for (pred.idx in 1:length(file.contents$Id)) {
    single.pred<-predict.one(pix, days, pred.idx)
    sos[pred.idx] <- find.sos(single.pred$Pred, percent.max)
  }
  filename<-paste("sos",year,".csv",sep="")
  cat("writing", filename)
  res=data.frame(Id=file.contents$Id, SOS=sos)
  write.csv(res,file=filename,quote=FALSE)
  return(res)
}


args <- commandArgs(trailingOnly = TRUE)
if (length(args)>0) {
  funcname <- args[1]
  year <- args[2]
  globalenv()[[funcname]](year)
}
