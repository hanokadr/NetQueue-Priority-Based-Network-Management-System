"""NetQueue backend: a small Flask REST API around netqueue_core.NetQueue."""

import threading

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from graphs import draw_graphs
from netqueue_core import NetQueue, ValidationError

app = Flask(__name__)
CORS(app)                       # lets the frontend (another origin) call this API

net = NetQueue()
lock = threading.Lock()         # Flask handles requests in threads; keep state safe


def handle(fn):
    """Run a handler under the lock and turn errors into JSON responses."""
    def wrapper(*args, **kwargs):
        try:
            with lock:
                return jsonify(fn(*args, **kwargs))
        except ValidationError as e:
            return jsonify({"error": str(e)}), e.status
        except Exception as e:                      # unexpected bug
            app.logger.exception(e)
            return jsonify({"error": "Server error"}), 500
    wrapper.__name__ = fn.__name__
    return wrapper


@app.get("/api/state")
@handle
def get_state():
    return net.get_state()


@app.post("/api/packets")
@handle
def add_packet():
    accepted, packet = net.add_packet(request.get_json(silent=True) or {})
    return {"accepted": accepted, "packet": packet.to_dict(), "state": net.get_state()}


@app.post("/api/packets/demo")
@handle
def demo_packets():
    results = [{"accepted": ok, "packet": p.to_dict()}
               for ok, p in net.generate_demo_packets()]
    return {"results": results, "state": net.get_state()}


@app.post("/api/transmit")
@handle
def transmit():
    packet = net.transmit_packet()
    return {"packet": packet.to_dict(), "state": net.get_state()}


@app.post("/api/packets/<packet_id>/delivered")
@handle
def delivered(packet_id):
    net.mark_delivered(packet_id)
    return {"state": net.get_state()}


@app.put("/api/settings")
@handle
def settings():
    net.set_settings(request.get_json(silent=True) or {})
    return {"state": net.get_state()}


@app.post("/api/reset")
@handle
def reset():
    net.reset()
    return {"state": net.get_state()}


@app.get("/api/graph.png")
def graph_png():
    """The backend draws the two graphs with matplotlib and returns them as one PNG image."""
    with lock:
        net.record_sample()
        points = list(net.history)
        capacity = net.max_queue_size
    theme = "dark" if request.args.get("theme") == "dark" else "light"
    png = draw_graphs(points, capacity, theme)
    return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
