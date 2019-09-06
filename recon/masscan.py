import logging

import luigi
from luigi.util import inherits
from luigi.contrib.external_program import ExternalProgramTask

from recon.targets import TargetList
from recon.config import top_tcp_ports, top_udp_ports, masscan_config


@inherits(TargetList)
class Masscan(ExternalProgramTask):
    """ Run masscan against a target specified via the TargetList Task.

    Masscan commands are structured like the example below.  When specified, --top_ports is processed and
    then ultimately passed to --ports.

    masscan -v --open-only --banners --rate 1000 -e tun0 -oJ masscan.tesla.json --ports 80,443,22,21 -iL tesla.ips

    The corresponding luigi command is shown below.

    PYTHONPATH=$(pwd) luigi --local-scheduler --module recon.masscan Masscan --target-file tesla --ports 80,443,22,21

    Args:
        rate: desired rate for transmitting packets (packets per second)
        interface: use the named raw network interface, such as "eth0"
        top_ports: Scan top N most popular ports
        ports: specifies the port(s) to be scanned
    """

    rate = luigi.Parameter(default=masscan_config.get("rate"))
    interface = luigi.Parameter(default=masscan_config.get("iface"))
    top_ports = luigi.IntParameter(default=0)  # IntParameter -> top_ports expected as int
    ports = luigi.Parameter(default="")

    def __init__(self, *args, **kwargs):
        super(Masscan, self).__init__(*args, **kwargs)
        self.masscan_output = f"masscan.{self.target_file}.json"

    def requires(self):
        """ Masscan depends on TargetList to run.

        TargetList expects target_file as a parameter.

        Returns:
            dict(str: TargetList)
        """
        return {"target_list": TargetList(target_file=self.target_file)}

    def output(self):
        """ Returns the target output for this task.

        Naming convention for the output file is masscan.TARGET_FILE.json.

        Returns:
            luigi.local_target.LocalTarget
        """
        return luigi.LocalTarget(self.masscan_output)

    def program_args(self):
        """ Defines the options/arguments sent to masscan after processing.

        Returns:
            list: list of options/arguments, beginning with the name of the executable to run
        """
        if self.ports and self.top_ports:
            # can't have both
            logging.error("Only --ports or --top-ports is permitted, not both.")
            exit(1)

        if not self.ports and not self.top_ports:
            # need at least one
            logging.error("Must specify either --top-ports or --ports.")
            exit(2)

        if self.top_ports < 0:
            # sanity check
            logging.error("--top-ports must be greater than 0")
            exit(3)

        if self.top_ports:
            # if --top-ports used, format the top_*_ports lists as strings and then into a proper masscan --ports option
            top_tcp_ports_str = ",".join(str(x) for x in top_tcp_ports[: self.top_ports])
            top_udp_ports_str = ",".join(str(x) for x in top_udp_ports[: self.top_ports])

            self.ports = f"{top_tcp_ports_str},U:{top_udp_ports_str}"
            self.top_ports = 0

        command = [
            "masscan",
            "-v",
            "--open",
            "--banners",
            "--rate",
            self.rate,
            "-e",
            self.interface,
            "-oJ",
            self.masscan_output,
            "--ports",
            self.ports,
            "-iL",
            self.input().get("target_list").path,
        ]

        return command
