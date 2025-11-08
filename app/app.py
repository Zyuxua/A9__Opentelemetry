import logging
import time
from flask import Flask, request
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

resource = Resource.create({"service.name": "ot-demo-flask"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

console_exporter = ConsoleSpanExporter()
console_processor = BatchSpanProcessor(console_exporter)
trace.get_tracer_provider().add_span_processor(console_processor)

otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
otlp_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(otlp_processor)

class TraceIdLogFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            record.otel_trace_id = format(ctx.trace_id, '032x')
        else:
            record.otel_trace_id = "none"
        return True

log_format = "[%(levelname)s] trace_id=%(otel_trace_id)s %(message)s"
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(log_format))
logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.addFilter(TraceIdLogFilter())

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)  

@app.route("/")
def index():
    logger.info("Handling index request")
    with tracer.start_as_current_span("index-work"):
        time.sleep(0.1)
        logger.info("Completed some work in index")
    return "Hello OpenTelemetry!"

@app.route("/chain")
def chain():
    logger.info("Handling chain request (parent+children spans)")
    with tracer.start_as_current_span("parent-span"):
        with tracer.start_as_current_span("child-span-1"):
            time.sleep(0.05)
            logger.info("Child 1 done")
        with tracer.start_as_current_span("child-span-2"):
            time.sleep(0.03)
            logger.info("Child 2 done")
    logger.info("Chain finished")
    return "Chained spans created"

@app.route("/call-service-b")
def call_service_b():
    logger.info("Calling service B")
    import requests
    try:
        r = requests.get("http://localhost:8001/")
        logger.info("Service B responded: %s", r.text)
    except Exception as e:
        logger.error("Failed to call service B: %s", str(e))
    return "Called service B"

if __name__ == "__main__":
    app.run(port=8000)
