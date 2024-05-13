#!/usr/bin/env python3

class FilterModule(object):
  def filters(self):
    return {
      'platforms': self.platforms,
      'dev_types': self.dev_types
    }

  def platforms(self, manufacturers):
    plist = []

    for m in manufacturers.keys():
      if( manufacturers[m] != None and 'platforms' in manufacturers[m].keys() ):
        for platform in manufacturers[m]['platforms']:
          plist.append( {'manufacturer' : m, 'platform' : platform })

    return plist

  def dev_types(self, manufacturers):
    plist = []

    for m in manufacturers.keys():
      if( manufacturers[m] != None and 'dev_types' in manufacturers[m].keys() ):
        for model in manufacturers[m]['dev_types']:
          plist.append( {'manufacturer' : m, 'model' : model })

    return plist
