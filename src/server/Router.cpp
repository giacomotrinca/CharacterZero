#include "server/Router.h"
#include "server/Json.h"
#include "domain/Schema.h"

#include <algorithm>
#include <cctype>
#include <optional>
#include <string>

namespace cz {

namespace {

constexpr size_t kMaxNameLength = 200;

void sendJson(httplib::Response& res, int status, const Json& body) {
    res.status = status;
    res.set_content(body.dump(), "application/json");
}

void sendError(httplib::Response& res, int status, const std::string& msg) {
    sendJson(res, status, {{"error", msg}});
}

std::optional<long long> parseId(const std::string& s) {
    if (s.empty()) return std::nullopt;
    try {
        size_t pos = 0;
        long long v = std::stoll(s, &pos);
        if (pos != s.size() || v < 0) return std::nullopt;
        return v;
    } catch (...) { return std::nullopt; }
}

std::string trim(std::string s) {
    auto notSpace = [](unsigned char c){ return !std::isspace(c); };
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), notSpace));
    s.erase(std::find_if(s.rbegin(), s.rend(), notSpace).base(), s.end());
    return s;
}

}

Router::Router(httplib::Server& server, SheetRepository& repo, const std::string& webRoot)
    : server_(server), repo_(repo), webRoot_(webRoot) {}

void Router::registerAll() {
    registerApi();
    registerStatic();
}

void Router::registerApi() {
    server_.Get("/api/health", [](const httplib::Request&, httplib::Response& res) {
        sendJson(res, 200, {{"status", "ok"}});
    });

    server_.Get("/api/schema", [](const httplib::Request&, httplib::Response& res) {
        sendJson(res, 200, Schema::toJson());
    });

    server_.Get("/api/sheets", [this](const httplib::Request&, httplib::Response& res) {
        Json arr = Json::array();
        for (const auto& s : repo_.list()) arr.push_back(s.toJsonSummary());
        sendJson(res, 200, arr);
    });

    server_.Get(R"(/api/sheets/(\d+))", [this](const httplib::Request& req, httplib::Response& res) {
        auto id = parseId(req.matches[1]);
        if (!id) { sendError(res, 400, "Invalid id"); return; }
        auto s = repo_.get(*id);
        if (!s) { sendError(res, 404, "Sheet not found"); return; }
        sendJson(res, 200, s->toJsonFull());
    });
    // Catch-all per ID non numerici
    server_.Get(R"(/api/sheets/(.+))", [](const httplib::Request&, httplib::Response& res) {
        sendError(res, 400, "Invalid id");
    });

    server_.Post("/api/sheets", [this](const httplib::Request& req, httplib::Response& res) {
        Json body = Json::parse(req.body, nullptr, false);
        if (body.is_discarded() || !body.is_object()) {
            sendError(res, 400, "Invalid JSON body"); return;
        }
        Sheet s;
        s.kind    = body.value("kind",    std::string{});
        s.subtype = body.value("subtype", std::string{});
        s.name    = trim(body.value("name", std::string{}));
        if (body.contains("data") && body["data"].is_object()) s.data = body["data"];

        if (!Schema::isValidKind(s.kind)) {
            sendError(res, 400, "Invalid kind"); return;
        }
        if (!Schema::isValidSubtypeFor(s.kind, s.subtype)) {
            sendError(res, 400, "Invalid subtype for kind"); return;
        }
        if (s.name.empty()) { sendError(res, 400, "Name required"); return; }
        if (s.name.size() > kMaxNameLength) {
            sendError(res, 400, "Name too long (max 200)"); return;
        }

        long long id = repo_.create(s);
        sendJson(res, 201, {{"id", id}});
    });

    server_.Put(R"(/api/sheets/(\d+))", [this](const httplib::Request& req, httplib::Response& res) {
        auto id = parseId(req.matches[1]);
        if (!id) { sendError(res, 400, "Invalid id"); return; }
        Json body = Json::parse(req.body, nullptr, false);
        if (body.is_discarded() || !body.is_object()) {
            sendError(res, 400, "Invalid JSON body"); return;
        }
        std::optional<std::string> name;
        std::optional<Json> data;
        if (body.contains("name") && body["name"].is_string()) {
            auto n = trim(body["name"].get<std::string>());
            if (n.empty())               { sendError(res, 400, "Name cannot be empty"); return; }
            if (n.size() > kMaxNameLength){ sendError(res, 400, "Name too long (max 200)"); return; }
            name = std::move(n);
        }
        if (body.contains("data") && body["data"].is_object()) data = body["data"];

        if (!repo_.update(*id, name, data)) { sendError(res, 404, "Sheet not found"); return; }
        res.status = 204;
    });
    server_.Put(R"(/api/sheets/(.+))", [](const httplib::Request&, httplib::Response& res) {
        sendError(res, 400, "Invalid id");
    });

    server_.Delete(R"(/api/sheets/(\d+))", [this](const httplib::Request& req, httplib::Response& res) {
        auto id = parseId(req.matches[1]);
        if (!id) { sendError(res, 400, "Invalid id"); return; }
        if (!repo_.remove(*id)) { sendError(res, 404, "Sheet not found"); return; }
        res.status = 204;
    });
    server_.Delete(R"(/api/sheets/(.+))", [](const httplib::Request&, httplib::Response& res) {
        sendError(res, 400, "Invalid id");
    });
}

void Router::registerStatic() {
    server_.set_mount_point("/", webRoot_);
    // Disabilita la cache del browser per i file statici (utile in sviluppo):
    // garantisce che modifiche a CSS/JS/HTML siano sempre prelevate fresche.
    server_.set_post_routing_handler([](const httplib::Request& req, httplib::Response& res) {
        if (req.path.rfind("/api/", 0) == 0) return; // API: non toccare
        res.set_header("Cache-Control", "no-cache, no-store, must-revalidate");
        res.set_header("Pragma", "no-cache");
        res.set_header("Expires", "0");
    });
}

}
