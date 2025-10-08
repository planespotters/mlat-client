# mlat-client

This is a client that selectively forwards Mode S messages to a
server that resolves the transmitter position by multilateration of the same
message received by multiple clients.

The corresponding server code is available at
https://github.com/planespotters/mlat-server.

## Building

Due to conflicting packages with the same name, it's recommended to install in a Python virtual environment.
First set the direcory you'd like to install to, if that path is not writeable by your user, use `sudo su` to become root first.
```
VENV=/usr/local/share/planespotters/venv
```
Now the build / install, it's not a bad idea to recreate the virtual environment when rebuilding:
```
rm -rf "$VENV"
python3 -m venv "$VENV"
source "$VENV/bin/activate"
python3 setup.py build
python3 setup.py install
```

To run it, invoke:
```
/usr/local/share/planespotters/venv/bin/mlat-client
```


## Running

To connect to a multilateration server, contact the server's administrator
for configuration instructions.

### Prerequisites

**IMPORTANT**: Before starting the mlat-client, ensure your ADS-B receiver/data source is running and accessible. The client requires an active connection to your receiver to function properly.

**Common receiver sources:**
- dump1090 / dump1090-fa / dump1090-mutability (typically on port 30005)
- readsb (typically on port 30005)
- Radarcape
- Mode-S Beast

**Verify receiver is running:**
```bash
# Check if your receiver is listening on the expected port
# (Replace 30005 with your actual port)
nc -zv localhost 30005
```

If this fails, start your receiver software before running mlat-client.

### Troubleshooting

#### Receiver connection issues

**Symptom**: Client logs "Receiver not connected" or "No data received for X seconds"

**Common causes:**
1. **Receiver not running** - Start your receiver software (dump1090, readsb, etc.)
2. **Wrong host/port** - Verify `--input-connect` matches your receiver's output port (usually localhost:30005)
3. **Firewall blocking connection** - Check firewall rules allow local connections
4. **Receiver output not configured** - Ensure receiver is configured to output Beast format data

**Check receiver status:**
```bash
# For dump1090-fa/readsb as a service
sudo systemctl status dump1090-fa
# or
sudo systemctl status readsb

# Check if receiver is outputting data
nc localhost 30005 | hexdump -C
# You should see data flowing. Press Ctrl+C to exit.
```

#### Data quality issues

**Symptom**: "Out-of-order timestamps" warnings

**Common causes:**
1. **Multiple receivers feeding one client** - Use separate mlat-client for each receiver
2. **Wrong input type** - Verify `--input-type` matches your receiver (try `radarcape_gps` or `dump1090`)

## Supported receivers

* Anything that produces Beast-format output with a 12MHz clock:
 * readsb, dump1090-mutability, dump1090-fa
 * an actual Mode-S Beast
 * airspy_adsb in Beast output mode
* Radarcape in 12MHz mode
* Radarcape in GPS mode

## Unsupported receivers

* The FlightRadar24 radarcape-based receiver. This produces a deliberately
crippled timestamp in its output, making it useless for multilateration.
If you have one of these, you should ask FR24 to fix this.

## License

Copyright 2015, [Oliver Jowett](mailto:oliver@mutability.co.uk).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received [a copy of the GNU General Public License](COPYING)
along with this program.  If not, see <http://www.gnu.org/licenses/>.
