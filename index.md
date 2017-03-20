## Installation

Currently, CAM4LINUX has to be installed manual. I will push a systemd service file and an PKGBUILD for ArchLinux soon!

## Configuration

Configuration is very simple! It follows a [JSON](https://en.wikipedia.org/wiki/JSON) like style!\\
The standart config is placed unter `/etc/cam4linux/config.json`.\\
Example config:
{% highlight %}
{
# CAM4LINUX example config file!
# Project home is right here: https://github.com/xvzf/cam4linux

# Let's add a new device!
# "Grid+" can be replaced by any UTF-8 formated string!
"Grid+": {
	"type": "grid",        # The device type
	"port": "/dev/ttyACM0" # Port (check dmesg when plugging in the Grid)
}
}

{% endhighlight %}

## Query devices

Currently the only way is via `camsensors.py`. It acts like the `sensor` command of `lm_sensors` and includes a basic interface to control fan speeds:

{% highlight Bash %}
usage: camsensors.py [-h] [--device DEVICE [DEVICE ...]] [--addr ADDR]
                     [--port PORT] [--set SET] [--value VALUE]
                     [--ports PORTS [PORTS ...]]

CAM4LINUX CLI

optional arguments:
  -h, --help            show this help message and exit
  --device DEVICE [DEVICE ...]
                        Select device
  --addr ADDR           Custom IP
  --port PORT           Custom Port
  --set SET             Set value for device
  --value VALUE         Value to set
  --ports PORTS [PORTS ...]
                        Select output ports
{% endhighlight %}
