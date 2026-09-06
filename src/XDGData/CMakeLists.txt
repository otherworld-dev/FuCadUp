include(GNUInstallDirs)

if(NOT DEFINED APPDATA_RELEASE_DATE)
    if(EXISTS "${CMAKE_SOURCE_DIR}/.git")
        execute_process(COMMAND git log -1 --pretty=%cd --date=short
            OUTPUT_VARIABLE APPDATA_RELEASE_DATE
            WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
            OUTPUT_STRIP_TRAILING_WHITESPACE)
    else()
        string(TIMESTAMP APPDATA_RELEASE_DATE "%Y-%m-%d")
    endif()
endif()

configure_file(
    org.fucadup.FuCadUp.metainfo.xml.in
    ${CMAKE_BINARY_DIR}/org.fucadup.FuCadUp.metainfo.xml
)
install(
    FILES ${CMAKE_BINARY_DIR}/org.fucadup.FuCadUp.metainfo.xml
    DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/metainfo
)

install(
    FILES org.fucadup.FuCadUp.desktop
    DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/applications
)

install(
    FILES org.fucadup.FuCadUp.xml
    DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/mime/packages
)

configure_file(
    FuCadUp.thumbnailer.in
    ${CMAKE_BINARY_DIR}/FuCadUp.thumbnailer
)
install(
    FILES ${CMAKE_BINARY_DIR}/FuCadUp.thumbnailer
    DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/thumbnailers
)

configure_file(
    ${CMAKE_SOURCE_DIR}/src/Tools/fucadup-thumbnailer.in
    ${CMAKE_BINARY_DIR}/fucadup-thumbnailer
)
install(
    PROGRAMS ${CMAKE_BINARY_DIR}/fucadup-thumbnailer
    TYPE BIN
)
