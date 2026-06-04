#pragma once
#include <httplib.h>
#include "domain/SheetRepository.h"
#include <string>

namespace cz {

class Router {
public:
    Router(httplib::Server& server, SheetRepository& repo, const std::string& webRoot);
    void registerAll();

private:
    void registerApi();
    void registerStatic();

    httplib::Server& server_;
    SheetRepository& repo_;
    std::string      webRoot_;
};

}
