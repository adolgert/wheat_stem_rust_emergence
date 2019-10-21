#include "config.hpp"

#include <iostream>

using namespace land_use;
using namespace std;

int main(int argc, char* argv[])
{
    cout << "cdls: " << config_get("cdls") << endl;

    return 0;
}
