"""
NetQueue core logic (same Python code as the Tkinter version, minus the GUI).

Priority scheduling uses a heap (heapq), FCFS uses a deque.
Priority rule: 5 = highest, 1 = lowest. Equal priorities are served in arrival order.
"""

import heapq
import ipaddress
import random
import time
from collections import deque

CAPACITIES = [3, 5, 10, 15, 20]
MODES = ["Priority", "FCFS"]
PROTOCOLS = ["TCP", "UDP", "ICMP"]


class ValidationError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ============================================================
# PACKET CLASS
# ============================================================

class Packet:
    def __init__(self, packet_id, source_ip, destination_ip,
                 protocol, size, priority, seq):
        self.packet_id = packet_id
        self.source_ip = source_ip
        self.destination_ip = destination_ip
        self.protocol = protocol
        self.size = size
        self.priority = priority
        self.seq = seq                       # arrival order (heap tie-breaker)
        self.arrival_time = time.time()
        self.status = "Waiting"              # Waiting / In Transit / Transmitted / Dropped
        self.queue_wait = 0.0

    def waiting_time(self):
        return time.time() - self.arrival_time

    def to_dict(self):
        return {
            "id": self.packet_id, "source": self.source_ip,
            "destination": self.destination_ip, "protocol": self.protocol,
            "size": self.size, "priority": self.priority,
            "status": self.status, "queueWait": self.queue_wait,
        }


# ============================================================
# NETQUEUE (the simulation)
# ============================================================

class NetQueue:

    def __init__(self):
        self.max_queue_size = 5
        self.mode = "Priority"
        self.version = 0                     # lets the frontend ignore stale responses
        self.boot = int(time.time() * 1000)  # changes whenever the server restarts
        self.reset()

    def reset(self):
        self.priority_queue = []             # heap of (-priority, seq, packet)
        self.fcfs_queue = deque()
        self.all_packets = []
        self.used_ids = set()
        self.seq_counter = 0

        self.generated_count = 0
        self.transmitted_count = 0
        self.dropped_count = 0
        self.total_waiting_time = 0.0
        self.total_transmitted_size = 0
        self.simulation_start_time = None

        self.logs = []
        self.history = deque(maxlen=100)     # graph samples (one per second)
        self.last_sample = 0.0
        self.log("Simulation reset.")

    # ---------------- helpers ----------------

    def log(self, message):
        self.logs.append({"t": int(time.time() * 1000), "msg": message})
        if len(self.logs) > 200:
            self.logs.pop(0)
        self.version += 1

    def next_free_id(self):
        number = 1
        while f"P{number:02d}" in self.used_ids:
            number += 1
        return f"P{number:02d}"

    def current_queue_size(self):
        if self.mode == "Priority":
            return len(self.priority_queue)
        return len(self.fcfs_queue)

    def waiting_packets(self):
        """Waiting packets in the order they will be transmitted."""
        if self.mode == "Priority":
            return [item[2] for item in sorted(self.priority_queue)]
        return list(self.fcfs_queue)

    def make_packet(self, packet_id, source, destination, protocol, size, priority):
        self.seq_counter += 1
        return Packet(packet_id, source, destination, protocol,
                      size, priority, self.seq_counter)

    # ---------------- queue operations ----------------

    def enqueue(self, packet):
        """Put a packet in the queue, or drop it if the queue is full.
        Returns True if accepted, False if dropped."""
        self.generated_count += 1
        self.used_ids.add(packet.packet_id)
        self.all_packets.append(packet)

        if self.simulation_start_time is None:
            self.simulation_start_time = time.time()

        if self.current_queue_size() >= self.max_queue_size:
            packet.status = "Dropped"
            self.dropped_count += 1
            self.log(f"{packet.packet_id} DROPPED - Queue is full.")
            return False

        if self.mode == "Priority":
            # Negative priority -> highest priority comes out first.
            heapq.heappush(self.priority_queue,
                           (-packet.priority, packet.seq, packet))
        else:
            self.fcfs_queue.append(packet)

        self.log(f"{packet.packet_id} added "
                 f"(Priority {packet.priority}, {packet.protocol}, "
                 f"{packet.size} KB)")
        return True

    def add_packet(self, data):
        packet_id = str(data.get("id") or "").strip()
        if not packet_id:
            raise ValidationError("Packet ID cannot be empty.")
        if packet_id in self.used_ids:
            raise ValidationError(f"Packet ID '{packet_id}' is already used.")

        source = str(data.get("source") or "").strip()
        destination = str(data.get("destination") or "").strip()
        try:
            ipaddress.IPv4Address(source)
        except ValueError:
            raise ValidationError("Source IP is not a valid IPv4 address.")
        try:
            ipaddress.IPv4Address(destination)
        except ValueError:
            raise ValidationError("Destination IP is not a valid IPv4 address.")

        protocol = data.get("protocol")
        if protocol not in PROTOCOLS:
            raise ValidationError("Protocol must be TCP, UDP or ICMP.")

        try:
            size = int(str(data.get("size", "")).strip())
        except ValueError:
            raise ValidationError("Packet size must be a whole number.")
        if size <= 0:
            raise ValidationError("Packet size must be greater than 0.")

        try:
            priority = int(str(data.get("priority", "")).strip())
        except ValueError:
            raise ValidationError("Priority must be a number from 1 to 5.")
        if priority < 1 or priority > 5:
            raise ValidationError("Priority must be between 1 and 5.")

        packet = self.make_packet(packet_id, source, destination,
                                  protocol, size, priority)
        accepted = self.enqueue(packet)
        return accepted, packet

    def generate_demo_packets(self):
        results = []
        for _ in range(5):
            packet = self.make_packet(
                self.next_free_id(),
                f"192.168.1.{random.randint(2, 100)}",
                f"192.168.1.{random.randint(101, 200)}",
                random.choice(PROTOCOLS),
                random.randint(100, 1000),
                random.randint(1, 5),
            )
            results.append((self.enqueue(packet), packet))
        return results

    def transmit_packet(self):
        """Take the next packet out of the queue. It is 'In Transit', NOT
        transmitted yet - it counts as transmitted when mark_delivered() runs."""
        if self.mode == "Priority":
            if not self.priority_queue:
                raise ValidationError("There are no packets waiting.", 409)
            _, _, packet = heapq.heappop(self.priority_queue)
        else:
            if not self.fcfs_queue:
                raise ValidationError("There are no packets waiting.", 409)
            packet = self.fcfs_queue.popleft()

        packet.queue_wait = packet.waiting_time()
        packet.status = "In Transit"
        self.log(f"{packet.packet_id} left the queue "
                 f"(waited {packet.queue_wait:.2f}s) - in transit...")
        return packet

    def mark_delivered(self, packet_id):
        """Called by the frontend when the packet reaches the destination."""
        packet = next((p for p in self.all_packets
                       if p.packet_id == packet_id and p.status == "In Transit"),
                      None)
        if packet is None:
            raise ValidationError("That packet is not in transit.", 409)

        packet.status = "Transmitted"
        self.transmitted_count += 1
        self.total_waiting_time += packet.queue_wait
        self.total_transmitted_size += packet.size

        self.log(f"{packet.packet_id} TRANSMITTED | "
                 f"Priority: {packet.priority} | "
                 f"Wait: {packet.queue_wait:.2f}s | Size: {packet.size} KB")

        if self.current_queue_size() == 0 and not any(
                p.status == "In Transit" for p in self.all_packets):
            self.log(f"ALL PACKETS TRANSMITTED - queue is empty "
                     f"({self.transmitted_count} sent, "
                     f"{self.dropped_count} dropped).")

    def set_settings(self, data):
        capacity = data.get("capacity")
        mode = data.get("mode")

        if capacity is not None:
            try:
                capacity = int(capacity)
            except (TypeError, ValueError):
                capacity = None
            if capacity not in CAPACITIES:
                raise ValidationError("Capacity must be 3, 5, 10, 15 or 20.")
        if mode is not None and mode not in MODES:
            raise ValidationError("Scheduling must be Priority or FCFS.")

        if capacity is not None:
            self.max_queue_size = capacity

        if mode is not None and mode != self.mode:
            # Move waiting packets to the other queue so none are lost.
            if mode == "Priority":
                packets = list(self.fcfs_queue)
                self.fcfs_queue.clear()
                for p in packets:
                    heapq.heappush(self.priority_queue, (-p.priority, p.seq, p))
            else:
                packets = sorted((item[2] for item in self.priority_queue),
                                 key=lambda p: p.seq)
                self.priority_queue.clear()
                self.fcfs_queue.extend(packets)
            self.mode = mode

        self.log(f"Settings: capacity {self.max_queue_size}, "
                 f"scheduling {self.mode}.")

    # ---------------- graph data ----------------

    def record_sample(self):
        """Store queue size and counters (at most once per second) for the graphs."""
        now = time.time()
        if now - self.last_sample < 1:
            return
        self.last_sample = now
        self.history.append({"time": now, "queue": self.current_queue_size(),
                             "transmitted": self.transmitted_count,
                             "dropped": self.dropped_count})

    # ---------------- state for the frontend ----------------

    def get_state(self):
        self.record_sample()
        def by(status):
            return [p for p in self.all_packets if p.status == status]

        queue_size = self.current_queue_size()
        usage = queue_size / self.max_queue_size if self.max_queue_size else 0

        average_wait = (self.total_waiting_time / self.transmitted_count
                        if self.transmitted_count else 0.0)

        throughput = 0.0
        if self.simulation_start_time is not None and self.transmitted_count:
            elapsed = time.time() - self.simulation_start_time
            if elapsed > 0:
                throughput = self.total_transmitted_size / elapsed

        if usage < 0.5:
            congestion = "LOW"
        elif usage < 0.8:
            congestion = "MEDIUM"
        else:
            congestion = "HIGH"

        return {
            "version": self.version,
            "boot": self.boot,
            "settings": {"capacity": self.max_queue_size, "mode": self.mode,
                         "nextId": self.next_free_id()},
            "waiting": [p.to_dict() for p in self.waiting_packets()],
            "inTransit": [p.to_dict() for p in by("In Transit")],
            "transmitted": [p.to_dict() for p in by("Transmitted")[-5:]],
            "dropped": [p.to_dict() for p in by("Dropped")[-5:]],
            "stats": {
                "generated": self.generated_count,
                "transmitted": self.transmitted_count,
                "dropped": self.dropped_count,
                "queueSize": queue_size,
                "averageWait": average_wait,
                "throughput": throughput,
                "congestion": congestion,
            },
            "log": self.logs,
        }
