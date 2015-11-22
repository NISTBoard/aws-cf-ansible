from ansible import utils, errors
import boto.ec2
import boto.cloudformation
import os
import sys
import time
import pickle

# region/stack/param
class LookupModule(object):
  def __init__(self, basedir=None, **kwargs):
    self.basedir = basedir
    self.cache_dir = os.path.join(os.environ['HOME'],'.stack_resources')
    self.cache_time = 60

  def check_cache(self, file):
    now = int(time.time())
    data = ''
    if os.path.isfile(file):
      # check time stamp of file
      if ( now - int(os.path.getmtime(file)) ) < self.cache_time:
        fh = open(file, 'r')
        data = pickle.load(fh)

    return data

  def get_regions(self):
    regions_cache = os.path.join(self.cache_dir, 'regions')
    regions = self.check_cache(regions_cache)
    if regions:
      pass
    else:
      try:
        regions = boto.ec2.regions()
        regions = [ r.name for r in regions ]
        fh = open(regions_cache, 'w')
        pickle.dump(regions, fh)
      except:
        raise errors.AnsibleError('Couldn\'t retrieve aws regions')

    return regions

  def get_stack_info(self, region, stack_name):
    stack_cache = os.path.join(self.cache_dir, region + '-' + stack_name)
    resources = self.check_cache(stack_cache)
    if resources:
      pass
    else:
      try:
        conn = boto.cloudformation.connect_to_region(region)
        stack = conn.list_stack_resources(stack_name_or_id=stack_name)
        next_token = stack.next_token
        while next_token:
          next_stack = conn.list_stack_resources(stack_name_or_id=stack_name, next_token=next_token)
          next_token = next_stack.next_token
          stack = stack + next_stack
        fh = open(stack_cache, 'w')
        resources = stack
        pickle.dump(resources, fh)
      except:
        resources = ''

    return resources

  def run(self, terms, inject=None, **kwargs):
    if not os.path.isdir(self.cache_dir):
      os.mkdir(self.cache_dir)

    regions = self.get_regions()

    args = terms.split('/')
    if args[0] in regions:
      region = args[0]
      stack_name = args[1]
      keys = args[2:]
    else:
      if 'AWS_REGION' in os.environ:
        region = os.environ['AWS_REGION']
        if not region in regions:
          raise errors.AnsibleError('%s is not a valid aws region' % region)
        stack_name = args[0]
        keys = args[1:]
      else:
        raise errors.AnsibleError('aws region not found in argument or AWS_REGION env var')

    resources = self.get_stack_info(region, stack_name)
    outputs = []

    if resources:
      resources = sorted(resources, key=lambda x: x.logical_resource_id)
      for obj in resources:
        if obj.logical_resource_id in keys:
          outputs.append(obj.physical_resource_id)

    if len(outputs) == 0:
      raise errors.AnsibleError('Nothing was retured by lookup')

    return outputs
