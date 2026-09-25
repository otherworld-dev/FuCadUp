// SPDX-License-Identifier: LGPL-2.1-or-later

#include "ViewVolumeCorrection.h"

#include <Inventor/nodes/SoCamera.h>

Gui::MappedView Gui::mappedViewVolume(const SoCamera& camera, const SbViewportRegion& viewport)
{
    Gui::MappedView mapped;
    // Coin 4.0.2, the system Coin on Ubuntu, reads the aspect ratio from this output argument
    // before it assigns it, so it has to go in already equal to the viewport; a default one
    // (100 x 100) made every view map as if it were square. The bundled Coin reads the input.
    mapped.viewport = viewport;
    mapped.volume = camera.getViewVolume(viewport, mapped.viewport);
    return mapped;
}
