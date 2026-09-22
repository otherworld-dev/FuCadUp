// SPDX-License-Identifier: LGPL-2.1-or-later

#include "ViewVolumeCorrection.h"

#include <Inventor/nodes/SoCamera.h>

Gui::MappedView Gui::mappedViewVolume(const SoCamera& camera, const SbViewportRegion& viewport)
{
    Gui::MappedView mapped;
    mapped.volume = camera.getViewVolume(viewport, mapped.viewport);
    return mapped;
}
