#!/usr/bin/env ruby

require 'date'

class Mailer
  def initialize()
    @strlen      = 80   # max string length
    @lines       = 250  # max lines
    @alpha       = [*('a'..'z'),*('A'..'Z'),*(0..9),"# $@%^&*;:,.?/-_=+()[]{}\|".chars].flatten
    @from_domain = "sub1.ctlabs.internal"
    @rcpt_domain = "ctlabs.internal"
  end

  def randstr()
    rand(@strlen).times.map { @alpha[rand(@alpha.size)] }.join
  end

  def send()
    lines = rand(@lines)
    @msg  = lines.times.map { randstr + "\n" }.join
    %x( echo -en '#{@msg}' | nl -ba | mail -s "#{lines} lines" -r sender#{rand(1000)}@#{@from_domain} mailer#{rand(10000)}@#{@rcpt_domain} )
  end
end

# Process.daemon

loop do
  threads = []
  tmax    = rand(50)

  for i in (0..tmax) do
    threads[i] = Thread.new { Mailer.new.send }
  end

  sleep(rand(3..30))

  for i in (0..tmax) do
    threads[i].join
  end
end
