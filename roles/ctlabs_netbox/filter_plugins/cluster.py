#!/usr/bin/env python3

class FilterModule(object):
  def filters(self):
    return {
      'cluster' : self.cluster
    }

  def cluster(self, cluster):
    clist = []

    for ctype in cluster.keys():
      for ctype_cluster in cluster[ctype]:
        ctype_cluster.update( {'type' : ctype } )
        clist.append(ctype_cluster)

    return clist
