"""Example 03: Microservices Architecture.

Demonstrates a 5-node microservices topology with API Gateway,
service mesh, message queue, and background worker.

Output: microservices.mp4
"""

from archmotion import Connection, FadeIn, Highlight, Node, Pulse, Queue, Scene, Transfer


def main() -> None:
    """Build and render a microservices architecture diagram."""
    # ── Create primitives ──
    gateway = Node("API Gateway")
    users_svc = Node("Users Service")
    payments_svc = Node("Payments Service")
    kafka = Queue("Kafka")
    worker = Node("Payment Worker")

    # ── Position layout ──
    users_svc.right_of(gateway, distance=4)
    payments_svc.below(gateway, distance=3)
    kafka.right_of(payments_svc, distance=4)
    worker.right_of(kafka, distance=4)

    # ── Connect nodes ──
    c_gw_users = Connection(gateway, users_svc, label="GET /users")
    c_gw_pay = Connection(gateway, payments_svc, label="POST /pay")
    c_pay_kafka = Connection(payments_svc, kafka, label="PaymentEvent")
    c_kafka_worker = Connection(kafka, worker, label="Consume")

    # ── Choreography ──
    scene = Scene(resolution="1080p", fps=60, theme="dark_terminal")

    # Step 1: Fade in all elements
    scene.play(FadeIn(
        gateway, users_svc, payments_svc, kafka, worker,
        c_gw_users, c_gw_pay, c_pay_kafka, c_kafka_worker,
    ))

    # Step 2: Client hits the gateway
    scene.play(Transfer(connection=c_gw_users, payload="GET /users"))

    # Step 3: Payment flow
    scene.play(Transfer(connection=c_gw_pay, payload="POST /pay"))
    scene.play(Pulse(target=payments_svc, color="#ff6b6b"))

    # Step 4: Async event through Kafka
    scene.play(Transfer(connection=c_pay_kafka, payload="PaymentEvent"))
    scene.play(Highlight(target=kafka, color="#facc15"))
    scene.play(Transfer(connection=c_kafka_worker, payload="Process"))

    # Step 5: Worker finishes
    scene.play(Pulse(target=worker, color="#22c55e"))

    scene.render("microservices.mp4")


if __name__ == "__main__":
    main()
