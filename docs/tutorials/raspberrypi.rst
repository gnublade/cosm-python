============
Raspberry PI
============

Try a Linux project with the Pi, and hook it up to Xively

Introduction
============

The Raspberry Pi (RPi) is a $35, credit-card sized computer that runs
a full Linux distribution, and can be used for many of the things that
you might use a normal desktop PC to do.  You can plug in USB
peripherals (keyboards, mice, etc.), output video via HDMI and DVI, or
even composite out to an old analogue TV; and it can be used for many of
the things that you might use a normal desktop PC to do.

Most importantly, it offers a capable and affordable prototyping
platform for a wide range of IoT products, with onboard ethernet (in the
Model B), plus a bunch of available GPIO (general purpose input/output)
pins. And because it runs a full Linux distribution, you have available
the enormous range of Linux libraries, software, and all other available
tools.

The GPIO pins have true general purpose input/outputs, I2C interface
pins (2-pin, SCL, SDA), SPI (MOSI, MISO, SCKL, select), serial Rx and Tx
for communication with serial peripherals, 2PWM and PPM.

Specs Overview: (Raspberry Model A)
-----------------------------------

================= ================
CPU               Broadcom BCM2835
Operating Voltage 5V
Digital I/O Pins  GPIO
Flash Memory      256 Mb RAM
Clock Speed       700 MHz
================= ================


Components
==========

To build this tutorial, you'll need the following components:

========================== ========
Raspberry Pi (Model B)     $35
4GB SD Card                $8
Ethernet cable             $3
Micro USB 5V Power adapter $5
Video output cable         OPTIONAL
USB keyboard               OPTIONAL
Monitor/TV                 OPTIONAL
========================== ========


Set up your Pi
==============

If you already have your RPi up and running, you can skip right ahead to
:ref:`code`.  But if you are using your RPi for the first
time, then read on for some suggestions about getting the board up and
running.

Before you can start using your board, you need to prepare your SD card
with the operating system for the Raspberry Pi. For our purposes we
recommend sticking with the default distribution, which is called
Raspbian. This is a Linux distribution based on the popular Debian
distribution, but optimized for the Rasberry Pi. You’ll find download
and installation instructions on the Raspberry Pi downloads page:

http://www.raspberrypi.org/downloads

Note: It is possible to purchase SD cards which are preloaded with the
Raspberry Pi operating system, but if you can't or don't want to this,
then the initialization steps to create a new bootable image from the
downloaded snapshot, are fairly straightforward.

Once you have an initialized SD card you need to:

1. Insert the SD card into the RPi (it should be inserted with the label
   facing down).
2. Plug an ethernet cable into the RPi to give it access to the web.
3. Connect the 5V power adapter to the RPi’s micro USB port.

As soon as the power supply is connected the red LED marked “PWR” will
turn on.  The other LEDs will blink in various patterns, and after
approximately 30 seconds, they’ll look like this:

.. image:: http://xively.com/images/tutorials/pi/booted_board.jpg

which means the RPi has booted and is ready to go.

If you’ve had the board hooked up to a monitor or TV, then you’ll have
seen some action during this boot process, and once the board has booted
for the first time, you should find yourself in the ``raspi-config``
window. This little script is designed to help you to configure your
board, and lets you do things like set the locale and time zone and many
other admin tasks. If you are trying to set up the board headless (i.e.
without an attached monitor), then read on.  Otherwise, skip ahead to
:ref:`configure`.

If you *don’t* have an external monitor, you'll instead need to
configure the RPi by typed commands.  Doing this requires a little bit
more work, but not too much. The only tricky part is finding out the IP
address of your RPi so that you can connect to it via the SSH protocol,
which lets you start the configuration process. If your RPi is plugged
into your router, then you should be able to obtain the IP address by
opening the router control panel and looking for its list of attached
devices. Alternatively, it’s possible to use a tool like nmap to scan
your LAN and find the IP address of the RPi.

Once you have its IP address, then you should SSH into the box:

::

    $ ssh pi@192.168.0.13

When you get a login prompt, login with the password ‘raspberry’. You
will then find yourself at a command prompt on the machine that looks
something like this:

::

    pi@raspberrypi ~ $

At this point you should run:

::

    $ sudo raspi-config

then you’ll be at the same stage as those booting with an attached
monitor.

.. _configure:

Configure your Pi
-----------------

.. image:: http://xively.com/images/tutorials/pi/raspi-config.png

At this point you can optionally change settings such as time zone and
locale if you want, but the one important thing you should do is:

1. Select ``expand_rootfs`` to expand the root filesystem to use all of
   the SD card.
2. Answer yes to a reboot.
3. When the RPi boots back up, login again.

At this point we’re ready to start developing our tutorial application.

.. _code:

Write some code!
================

We’re going to try writing a little Python demo app that reads the
current load average from the board, and then publishes this value to
a Xively feed. We’re going to assume in writing this that you are
comfortable with editing code on the command line using an editor like
Vim or Emacs, but if you have a monitor and attached keyboard/mouse, you
can of course start the full desktop environment on the RPi, and use
a more visual editor to edit the code.

However, even if you aren't editing the code directly from the command
line, you will still need command line access, as there are some
commands you'll need to execute from the command line to get things
working.

We'll also be assuming you are logged into your board as the ``pi``
user, as this is the default user account automatically set up on the
board.  If you have created a new user account that you are using, then
it's fine to use that account instead, though you'll need to make sure
the account you are using also has super user permissions. Alternatively
you can just use the ``pi`` account for any commands that start with
``sudo``, and for everything else your non super user account is fine.

Install system packages
-----------------------

Before we get started with our little example library, there are a few
installation tasks you should probably do to get started.

First of all, let's update the system software:

::

    $ sudo apt-get update
    $ sudo apt-get upgrade

Your Raspberry Pi will already have a suitable version of Python
installed, however you'll also need to install the `Git version control
system <http://git-scm.com/>`_, to pull down the latest version of our
library from Github. Fortunately on the Raspberry Pi this is as simple
as running:

::

    $ sudo apt-get install git

Next let’s install some system level packages to that will let us build
our little app in a clean way.

::

    $ sudo apt-get install python-setuptools
    $ sudo easy_install pip
    $ sudo pip install virtualenv

Now these packages are installed, we don't need to install anything else
at the system level.


Start building the app
----------------------

Everything else we’re going to install at this point will be installed
inside a `virtualenv <https://pypi.python.org/pypi/virtualenv>`_. If you
aren’t familiar with virtualenv, there are many resources on it
elsewhere, and it's worth getting to grips with it for python
development. For our purposes however, you should be able to just follow
along by copying the commands below.  The point is to create an isolated
environment containing just the dependencies we need that doesn’t
interfere with any other applications on the box.

So first let's create a directory in which we're going to work:

::

    $ mkdir xively_tutorial
    $ cd xively_tutorial

We'll create a new virtualenv within this directory:

::

    $ virtualenv .envs/venv

This creates an isolated python environment within the ``.envs/venv``
folder, but before we can start using it, we need to tell the current
shell that this is the python environment we want to use. We do this by
'activating' the virtualenv:

::

    $ source .envs/venv/bin/activate

At this prompt you should notice that your prompt has changed,
indicating that we are now using the ``venv`` python.

Now can go ahead and install the Xively python library within our
virtualenv:

::

    $ pip install xively-python

This command should run for a few seconds, and you should see that it
installs the Xively library, plus any dependencies that it requires, and
you should also note that these dependencies are installed locally into
the virtualenv.

At this point we're almost ready to start writing our app, but before we
do that we should create a Device and Feed on Xively.

Create a Device and Feed on Xively
----------------------------------

1. Open a web browser on your computer.
2. Navigate to Develop.
3. Add a new device. Call it “Raspberry Pi”, and set its privacy to
   ‘private’.
4. On the device workbench take note of the Feed I, and Development API
   key that were automatically created for you as we’ll need them to get
   the RPi publishing data to the feed.


Write the code
--------------

1. Within the xively_tutorial directory, use your favourite editor to
   create a file called xively_tutorial.py.
2. Enter the following code into xively_tutorial.py:

.. literalinclude:: ../../examples/xively_tutorial.py
    :linenos:

Run the script:

1. Pass into the script as environment variables the Feed ID and API key
   you created earlier.
2. Pass in a DEBUG environment variable so that the script is a bit more
   chatty about what it’s doing.
3. Enter a command like this:

::

    $ export FEED_ID=12345
    $ export API_KEY=9MzbRooFNPJIy3zxVNRPUPll4JGSAKxsMmg4STZHbzNKTT0g
    $ export DEBUG=true
    $ python xively_tutorial.py

If all has gone according to plan the script should start without
errors, and start printing out its debug messages.

If you get any errors at this point, make sure that you have properly
activated your virtualenv, and that the Xively library plus dependencies
are all installed properly.


Watch the Workbench
===================

Hopefully you still have the device workbench still open in your
browser, but if not than then reopen it. With the python script running
on your Raspberry Pi you should now start to see requests coming through
into the request log, and you should start to see the value of your
load_avg channel updating in real time.

.. image: http://xively.com/images/tutorials/pi/raspberry_pi_workbench.png


Take this code and run!
=======================

This starter code shows you the basics how to pull data from the
Raspberry Pi, and send it to Xively using our Python library.  From
here, the opportunities are endless. Give these ideas a try:

- Hook up some real sensors to the Raspberry Pi's GPIO pins, and push
  this data to Xively.

- Get your python script running as a service so that it automatically
  runs when your RPi boots.

- Use your Raspberry Pi to subscribe to an existing feed over MQTT, and
  have it control or activate things in response to changes in that
  feed.
