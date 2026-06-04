#pragma once
#include <SQLiteCpp/SQLiteCpp.h>
#include <filesystem>
#include <memory>
#include <string>

namespace cz {

class Database {
public:
    Database(const std::filesystem::path& dbFile,
             const std::filesystem::path& migrationsDir);

    SQLite::Database& handle() { return *db_; }

private:
    void runMigrations(const std::filesystem::path& migrationsDir);
    int  currentVersion();
    void setVersion(int v);

    std::unique_ptr<SQLite::Database> db_;
};

}
