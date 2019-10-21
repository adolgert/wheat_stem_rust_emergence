# This is supposed to read the project configuration files. Try a sample:
#
# [General]
# datadir=/media/data0
# state=%(datadir)s/gimms/sample.tif
#
# And you can have more than one file, where the last read wins.

read.config<-function(filename) {
  conf.vars<-new.env()
  for (f in filename) {
    if (file.exists(f)) {
      header<-1
      key.val<-read.table(f, sep="=", col.names=c("key","value"), skip=header, as.is=c(1,2))
      for (kidx in seq(length(key.val$key))) {
        val<-key.val[["value"]][kidx]
        r<-regexpr("%[(]([a-zA-Z0-9]+)[)]",val)
        if (r>0) {
          rend<-attr(r,"match.length")
          sub.name<-substr(val,r+2,rend-1)
          if (exists(sub.name, envir=conf.vars)) {
            val<-paste(substr(val,0,r-1),conf.vars[[sub.name]],substr(val,rend+2,nchar(val)), sep="")
          }
        }
        assign(key.val[["key"]][kidx], val, envir=conf.vars)
      }
    }
  }
  return(conf.vars)
}

get.config<-function(name) {
  kv.env=read.config(c("project.cfg","project_local.cfg"))
  return(kv.env[[name]])
}
