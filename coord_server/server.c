/*
 * Robot Coordination Server
 *
 * Central HTTP server that bridges a camera node (person detection)
 * and a telemetry node (robot position/commands) on the same LAN.
 *
 * Endpoints:
 *   POST /detection   camera sends: {"detected": true, "confidence": 0.95}
 *   POST /telemetry   robot  sends: {"x": 1.0, "y": 2.0, "heading": 0.5}
 *   GET  /command     robot  polls: returns {"command":"hold"} or {"command":"move"}
 *   GET  /status      health check / full state dump
 *
 * Logic: when a person is detected the robot receives "hold" on /command.
 *        If no new detection arrives within HOLD_TIMEOUT_SEC the hold is released.
 *
 * Build:  gcc -Wall -O2 -pthread -o server server.c
 * Run:    ./server [port]          (default port: 8080)
 *
 * Quick test with curl:
 *   curl -X POST http://SERVER_IP:8080/detection  -d '{"detected":true,"confidence":0.9}'
 *   curl http://SERVER_IP:8080/command
 *   curl http://SERVER_IP:8080/status
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <signal.h>
#include <time.h>
#include <errno.h>

#define DEFAULT_PORT     8080
#define BACKLOG          16
#define BUF_SIZE         8192
#define HOLD_TIMEOUT_SEC 3   /* release hold if no detection for this many seconds */

/* ---- shared state ---- */

typedef struct {
    int    person_detected;
    float  confidence;
    time_t last_detection;

    float  pos_x, pos_y, heading;
    time_t last_telemetry;

    pthread_mutex_t mu;
} State;

static State g = { .mu = PTHREAD_MUTEX_INITIALIZER };
static volatile int g_running = 1;

/* ---- minimal JSON field extraction ---- */

static int json_bool(const char *json, const char *key)
{
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char *p = strstr(json, needle);
    if (!p) return -1;
    p += strlen(needle);
    while (*p == ' ' || *p == ':') p++;
    if (strncmp(p, "true",  4) == 0) return 1;
    if (strncmp(p, "false", 5) == 0) return 0;
    return -1;
}

static float json_float(const char *json, const char *key)
{
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char *p = strstr(json, needle);
    if (!p) return 0.0f;
    p += strlen(needle);
    while (*p == ' ' || *p == ':') p++;
    return strtof(p, NULL);
}

/* ---- HTTP helpers ---- */

static void send_json(int fd, int status, const char *body)
{
    const char *txt = status == 200 ? "OK" :
                      status == 400 ? "Bad Request" :
                      status == 404 ? "Not Found" : "Internal Server Error";
    char hdr[256];
    int  hlen = snprintf(hdr, sizeof(hdr),
        "HTTP/1.1 %d %s\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %zu\r\n"
        "Connection: close\r\n"
        "\r\n",
        status, txt, strlen(body));
    write(fd, hdr,  hlen);
    write(fd, body, strlen(body));
}

/* Returns pointer to body inside buf; sets *content_length from header. */
static const char *parse_request(const char *buf, char *method, char *path,
                                  int *content_length)
{
    if (sscanf(buf, "%15s %255s", method, path) != 2) return NULL;

    *content_length = 0;
    const char *cl = strcasestr(buf, "Content-Length:");
    if (cl) { cl += 15; while (*cl == ' ') cl++; *content_length = atoi(cl); }

    const char *body = strstr(buf, "\r\n\r\n");
    return body ? body + 4 : NULL;
}

/* ---- route handlers ---- */

static void route_post_detection(int fd, const char *body)
{
    if (!body) { send_json(fd, 400, "{\"error\":\"empty body\"}"); return; }

    int   det  = json_bool(body,  "detected");
    float conf = json_float(body, "confidence");

    if (det < 0) { send_json(fd, 400, "{\"error\":\"missing 'detected'\"}"); return; }

    pthread_mutex_lock(&g.mu);
    g.person_detected = det;
    g.confidence      = conf > 0.0f ? conf : (det ? 1.0f : 0.0f);
    if (det) g.last_detection = time(NULL);
    pthread_mutex_unlock(&g.mu);

    printf("[detection] person=%-3s  confidence=%.2f\n", det ? "YES" : "no", conf);
    send_json(fd, 200, "{\"status\":\"ok\"}");
}

static void route_post_telemetry(int fd, const char *body)
{
    if (!body) { send_json(fd, 400, "{\"error\":\"empty body\"}"); return; }

    float x = json_float(body, "x");
    float y = json_float(body, "y");
    float h = json_float(body, "heading");

    pthread_mutex_lock(&g.mu);
    g.pos_x          = x;
    g.pos_y          = y;
    g.heading        = h;
    g.last_telemetry = time(NULL);
    pthread_mutex_unlock(&g.mu);

    printf("[telemetry] x=%.2f  y=%.2f  heading=%.2f\n", x, y, h);
    send_json(fd, 200, "{\"status\":\"ok\"}");
}

static void route_get_command(int fd)
{
    pthread_mutex_lock(&g.mu);
    int    det  = g.person_detected;
    time_t last = g.last_detection;
    pthread_mutex_unlock(&g.mu);

    int hold = det && (time(NULL) - last < HOLD_TIMEOUT_SEC);

    if (hold)
        send_json(fd, 200, "{\"command\":\"hold\",\"reason\":\"person_detected\"}");
    else
        send_json(fd, 200, "{\"command\":\"move\"}");
}

static void route_get_status(int fd)
{
    pthread_mutex_lock(&g.mu);
    int    det      = g.person_detected;
    float  conf     = g.confidence;
    long   det_age  = det ? (long)(time(NULL) - g.last_detection)  : -1;
    float  x = g.pos_x, y = g.pos_y, h = g.heading;
    long   tel_age  = g.last_telemetry ? (long)(time(NULL) - g.last_telemetry) : -1;
    pthread_mutex_unlock(&g.mu);

    int hold = det && det_age >= 0 && det_age < HOLD_TIMEOUT_SEC;

    char body[512];
    snprintf(body, sizeof(body),
        "{"
          "\"person_detected\":%s,"
          "\"confidence\":%.2f,"
          "\"detection_age_sec\":%ld,"
          "\"command\":\"%s\","
          "\"telemetry\":{"
            "\"x\":%.3f,"
            "\"y\":%.3f,"
            "\"heading\":%.3f,"
            "\"age_sec\":%ld"
          "}"
        "}",
        det ? "true" : "false", conf, det_age,
        hold ? "hold" : "move",
        x, y, h, tel_age);

    send_json(fd, 200, body);
}

/* ---- per-connection thread ---- */

typedef struct { int fd; char ip[INET_ADDRSTRLEN]; } ConnArg;

static void *handle_conn(void *arg)
{
    ConnArg *ca = arg;
    int      fd = ca->fd;
    char     ip[INET_ADDRSTRLEN];
    strncpy(ip, ca->ip, sizeof(ip));
    free(ca);

    char buf[BUF_SIZE];
    int  received = 0;

    /* read until we have complete headers + full body */
    while (received < (int)sizeof(buf) - 1) {
        int n = read(fd, buf + received, sizeof(buf) - 1 - received);
        if (n <= 0) goto done;
        received += n;
        buf[received] = '\0';

        const char *sep = strstr(buf, "\r\n\r\n");
        if (!sep) continue;

        int content_length = 0;
        const char *cl = strcasestr(buf, "Content-Length:");
        if (cl) { cl += 15; while (*cl == ' ') cl++; content_length = atoi(cl); }

        int body_rcvd = received - (int)((sep + 4) - buf);
        if (body_rcvd >= content_length) break;
    }
    buf[received] = '\0';

    char        method[16], path[256];
    int         clen;
    const char *body = parse_request(buf, method, path, &clen);

    printf("[%s] %s %s\n", ip, method, path);

    if      (strcmp(method,"POST")==0 && strcmp(path,"/detection")==0) route_post_detection(fd, body);
    else if (strcmp(method,"POST")==0 && strcmp(path,"/telemetry" )==0) route_post_telemetry(fd, body);
    else if (strcmp(method,"GET" )==0 && strcmp(path,"/command"   )==0) route_get_command(fd);
    else if (strcmp(method,"GET" )==0 && strcmp(path,"/status"    )==0) route_get_status(fd);
    else    send_json(fd, 404, "{\"error\":\"unknown endpoint\"}");

done:
    close(fd);
    return NULL;
}

/* ---- signal & main ---- */

static void on_signal(int s) { (void)s; g_running = 0; }

int main(int argc, char *argv[])
{
    int port = (argc > 1) ? atoi(argv[1]) : DEFAULT_PORT;

    signal(SIGINT,  on_signal);
    signal(SIGTERM, on_signal);
    signal(SIGPIPE, SIG_IGN);

    int srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { perror("socket"); return 1; }

    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family      = AF_INET,
        .sin_addr.s_addr = INADDR_ANY,
        .sin_port        = htons((uint16_t)port)
    };

    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0) { perror("bind");   return 1; }
    if (listen(srv, BACKLOG) < 0)                              { perror("listen"); return 1; }

    printf("Robot coordination server  port=%d  hold_timeout=%ds\n\n", port, HOLD_TIMEOUT_SEC);
    printf("  POST /detection   {\"detected\":true,\"confidence\":0.9}\n");
    printf("  POST /telemetry   {\"x\":1.0,\"y\":2.0,\"heading\":0.5}\n");
    printf("  GET  /command     -> {\"command\":\"hold\"} or {\"command\":\"move\"}\n");
    printf("  GET  /status      -> full state\n\n");

    while (g_running) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(srv, &rfds);
        struct timeval tv = { .tv_sec = 1, .tv_usec = 0 };
        if (select(srv + 1, &rfds, NULL, NULL, &tv) <= 0) continue;

        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int cfd = accept(srv, (struct sockaddr *)&client_addr, &client_len);
        if (cfd < 0) { if (errno != EINTR) perror("accept"); continue; }

        ConnArg *ca = malloc(sizeof(ConnArg));
        ca->fd = cfd;
        inet_ntop(AF_INET, &client_addr.sin_addr, ca->ip, sizeof(ca->ip));

        pthread_t       tid;
        pthread_attr_t  attr;
        pthread_attr_init(&attr);
        pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
        if (pthread_create(&tid, &attr, handle_conn, ca) != 0) {
            perror("pthread_create");
            close(cfd);
            free(ca);
        }
        pthread_attr_destroy(&attr);
    }

    close(srv);
    printf("Server stopped.\n");
    return 0;
}
