import React, { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'

function DummyScene(){
  return (
    <mesh>
      <sphereGeometry args={[1.2, 64, 64]} />
      <meshStandardMaterial color="#C9A24B" metalness={0.8} roughness={0.2} />
    </mesh>
  )
}

export default function R3FScene(){
  return (
    <Canvas camera={{position:[0,0,4]}}>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5,5,5]} intensity={1} />
      <Suspense fallback={<Html>Loading 3D...</Html>}>
        <DummyScene />
      </Suspense>
      <OrbitControls enableZoom={false} enablePan={false} />
    </Canvas>
  )
}
