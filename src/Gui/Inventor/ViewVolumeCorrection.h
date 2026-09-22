// SPDX-License-Identifier: LGPL-2.1-or-later

#ifndef GUI_INVENTOR_VIEWVOLUMECORRECTION_H
#define GUI_INVENTOR_VIEWVOLUMECORRECTION_H

#include <Inventor/SbViewportRegion.h>
#include <Inventor/SbViewVolume.h>

class SoCamera;

namespace Gui
{

/** The camera's view volume, corrected for how the viewport maps onto it.
 *
 * A camera's own view volume is not what gets rendered: SoCamera::viewportMapping
 * decides how the volume meets a viewport that is a different shape. With the
 * default ADJUST_CAMERA and a viewport taller than it is wide, the volume is
 * expanded by 1/aspect - which is why a tall window shows more of the scene
 * instead of a squashed version of it. Projecting a point through the uncorrected
 * volume therefore lands somewhere the point was never drawn.
 *
 * \a mappedViewport receives the viewport the returned volume maps onto, which the
 * CROP_VIEWPORT_* modes narrow; project to pixels against that, not the original.
 */
SbViewVolume mappedViewVolume(const SoCamera& camera,
                              const SbViewportRegion& viewport,
                              SbViewportRegion& mappedViewport);

}  // namespace Gui

#endif  // GUI_INVENTOR_VIEWVOLUMECORRECTION_H
