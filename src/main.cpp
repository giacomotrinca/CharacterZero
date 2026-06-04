#include "db/Database.h"
#include "domain/SheetRepository.h"
#include "server/Router.h"

#include <httplib.h>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <string>

namespace fs = std::filesystem;

namespace {
httplib::Server* g_server = nullptr;

void handleSignal(int) {
    if (g_server) g_server->stop();
}

const char* envOr(const char* key, const char* fallback) {
    const char* v = std::getenv(key);
    return (v && *v) ? v : fallback;
}
}

int main() {
    try {
        fs::path dataDir       = CZ_DATA_DIR;
        fs::path migrationsDir = CZ_MIGRATIONS_DIR;
        std::string webRoot    = CZ_WEB_ROOT;

        cz::Database db(dataDir / "characterzero.db", migrationsDir);
        cz::SheetRepository repo(db);

        httplib::Server server;
        server.set_payload_max_length(1 * 1024 * 1024); // 1 MiB

        server.set_logger([](const httplib::Request& req, const httplib::Response& res) {
            std::printf("[http] %s %s -> %d (%zu bytes)\n",
                        req.method.c_str(), req.path.c_str(), res.status, res.body.size());
            std::fflush(stdout);
        });

        cz::Router router(server, repo, webRoot);
        router.registerAll();

        g_server = &server;
        std::signal(SIGINT,  handleSignal);
        std::signal(SIGTERM, handleSignal);

        const char* host = envOr("CZ_HOST", "127.0.0.1");
        int port = std::atoi(envOr("CZ_PORT", "8080"));
        if (port <= 0 || port > 65535) port = 8080;

        std::printf("CharacterZero listening on http://%s:%d\n", host, port);
        std::fflush(stdout);
        if (!server.listen(host, port)) {
            std::fprintf(stderr, "Failed to bind %s:%d\n", host, port);
            return 1;
        }
        std::printf("CharacterZero stopped.\n");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Fatal: %s\n", e.what());
        return 1;
    }
}
