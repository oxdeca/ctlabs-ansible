#!/usr/bin/env ruby

require 'date'
require 'time'
require 'fileutils'

class Files
  @@date      = Date.parse( "2011/01/01" ) # start date, used to create subdirs with

  def initialize()
    @strlen     = 80                         # max string length
    @lines      = 250                        # max lines
    @prefix     = "file"                     # file prefix
    @logdir     = "/opt/splunk-data/tmp"
    @alpha      = [*('a'..'z'),*('A'..'Z'),*(0..9),"# $@%^&*;:,.?/-_=+()[]{}\|".chars].flatten
  end

  def line(tag)
    #Time.now().to_s + " - #{tag} - " + randstr
    Time.now.utc.iso8601(6) + " - #{tag} - " + randstr
  end

  def inc_date()
    @@date += 1
  end

  def randstr()
    rand(@strlen).times.map { @alpha[rand(@alpha.size)] }.join
  end

  def create()
    fname = "#{@prefix}_#{rand(1000000)}"
    FileUtils.mkpath("#{@logdir}/#{@@date}")
    File.open( "#{@logdir}/#{@@date}/#{fname}", "w" ) do |f|
      f.puts( rand(@lines).times.map { line('files') + "\n" }.join )
    end
  end
end


# Process.daemon

loop do
  threads = []
  tmax    = 50

  for i in (0..tmax) do
    threads[i] = Thread.new { Files.new.create }
  end

  sleep(rand(3..10))

  for i in (0..tmax) do
    threads[i].join
  end
  Files.new.inc_date
end
