#!/usr/bin/env ruby

require 'date'
require 'time'

class Logger
  def initialize()
    @strlen  = 80 # max string length
    @lines   = 10 # max lines
    @logfile = "sampledpricing"
    @logdir  = "/var/sampled-pricing/logs"
    @alpha   = [*('a'..'z'),*('A'..'Z'),*(0..9),"# $@%^&*;:,.?/-_=+()[]{}\|".chars].flatten
  end

  def line(tag)
    #Time.now().to_s + " - #{tag} - " + randstr
    Time.now.utc.iso8601(6) + " - #{tag} - " + randstr
  end

  def randstr()
    rand(@strlen).times.map { @alpha[rand(@alpha.size)] }.join
  end

  def log()
    File.open( "#{@logdir}/#{@logfile}.#{Date.today.strftime("%Y.%m.%d")}.#{Time.now.strftime("%H")}.log", "a" ) do |log|
      log.puts( rand(@lines).times.map { line('log') + "\n" }.join )
    end

    File.open( "#{@logdir}/#{@logfile}-out.log", "a" ) do |out|
      out.puts( rand(@lines).times.map { line('out') + "\n" }.join )
    end

    File.open( "#{@logdir}/#{@logfile}-err.log", "a" ) do |err|
      err.puts( rand(@lines).times.map { line('err') + "\n" }.join )
    end
  end
end


# Process.daemon

loop do
  threads = []
  tmax    = 1

  for i in (0..tmax) do
    threads[i] = Thread.new { Logger.new.log }
  end

  sleep(rand(3..10))

  for i in (0..tmax) do
    threads[i].join
  end
end
