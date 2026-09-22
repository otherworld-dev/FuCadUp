// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#ifndef _PreComp_
#include <Inventor/nodes/SoCamera.h>
#endif

#include "ViewVolumeCorrection.h"

SbViewVolume Gui::mappedViewVolume(const SoCamera& camera,
                                   const SbViewportRegion& viewport,
                                   SbViewportRegion& mappedViewport)
{
    return camera.getViewVolume(viewport, mappedViewport);
}
